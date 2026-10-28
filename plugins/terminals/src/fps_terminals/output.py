"""Keep terminal state independently of the attached WebSockets."""

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import structlog
from anyio import (
    TASK_STATUS_IGNORED,
    CancelScope,
    Lock,
    WouldBlock,
    create_memory_object_stream,
    current_time,
    fail_after,
    move_on_after,
)
from anyio.abc import TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from fastapi import WebSocket, WebSocketDisconnect
from ghostty import GhosttyError, Terminal  # type: ignore[import-untyped]

log = structlog.get_logger()

# Network sends run in a separate task for each client.
SEND_TIMEOUT = 1
RESTORE_TIMEOUT = 10
# Even JSON's six-byte Unicode escapes stay below 64 KiB per message.
OUTPUT_CHUNK = 8192
OUTPUT_QUEUE_SIZE = 256
MAX_COLUMNS = 500
MAX_ROWS = 500
MAX_CELLS = 100_000


def valid_size(columns: int, rows: int) -> bool:
    return (
        type(columns) is int
        and type(rows) is int
        and 0 < columns <= MAX_COLUMNS
        and 0 < rows <= MAX_ROWS
        and columns * rows <= MAX_CELLS
    )


@dataclass
class _Client:
    send: MemoryObjectSendStream[list[Any]]
    receive: MemoryObjectReceiveStream[list[Any]]
    scope: CancelScope = field(default_factory=CancelScope)
    failed: bool = False
    snapshot: str | None = None


class TerminalOutput:
    def __init__(self, detach: Callable[[WebSocket], None]):
        self.emulator = Terminal(cols=80, rows=24)
        self.lock = Lock()
        self.websockets: list[WebSocket] = []
        self._clients: dict[WebSocket, _Client] = {}
        self._ready: set[WebSocket] = set()
        self._pending: dict[WebSocket, float] = {}
        self._detach = detach
        self.closed = False

    async def setup(self, websocket: WebSocket) -> None:
        async with self.lock:
            if self.closed:
                return
            send, receive = create_memory_object_stream[list[Any]](OUTPUT_QUEUE_SIZE)
            self._clients[websocket] = _Client(send, receive)
            self.websockets.append(websocket)
            self._enqueue(websocket, "setup", {})

    async def receive(self, websocket: WebSocket) -> Any:
        if websocket not in self._ready and websocket not in self._pending:
            # JupyterLab sends a size when opening a widget, but an existing
            # widget may reconnect its socket without sending another size.
            with move_on_after(1):
                return await websocket.receive_json()
            async with self.lock:
                await self.restore(websocket)
        if websocket in self._pending:
            try:
                with fail_after(max(0, self._pending[websocket] - current_time())):
                    return await websocket.receive_json()
            except TimeoutError:
                if websocket in self._pending:
                    await self._disconnect(websocket)
                    raise WebSocketDisconnect(code=1013) from None
                # PTY output may have completed restoration while receive waited.
        return await websocket.receive_json()

    async def _disconnect(self, websocket: WebSocket) -> None:
        client = self._clients.get(websocket)
        if client is not None:
            client.failed = True
        self._detach(websocket)

    def _enqueue(self, websocket: WebSocket, kind: str, data: Any) -> None:
        client = self._clients[websocket]
        try:
            if kind == "stdout":
                for start in range(0, len(data), OUTPUT_CHUNK):
                    client.send.send_nowait([kind, data[start : start + OUTPUT_CHUNK]])
            else:
                client.send.send_nowait([kind, data])
        except WouldBlock:
            # Never wait for network backpressure while holding the output lock.
            client.failed = True
            self._detach(websocket)
            raise WebSocketDisconnect(code=1013) from None

    async def send(
        self,
        websocket: WebSocket,
        connection_scope: CancelScope,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
    ) -> None:
        """One sender owns network output; queue order matches emulator order."""
        client = self._clients.get(websocket)
        task_status.started()
        if client is None:
            return
        try:
            with client.scope:
                async with client.receive:
                    async for message in client.receive:
                        if message[0] == "snapshot":
                            snapshot = client.snapshot
                            client.snapshot = None
                            assert snapshot is not None
                            for start in range(0, len(snapshot), OUTPUT_CHUNK):
                                with fail_after(SEND_TIMEOUT):
                                    await websocket.send_json(
                                        ["stdout", snapshot[start : start + OUTPUT_CHUNK]]
                                    )
                            del snapshot
                        else:
                            with fail_after(SEND_TIMEOUT):
                                await websocket.send_json(message)
        except Exception:
            client.failed = True
        finally:
            self._detach(websocket)
            if client.failed:
                # Cancellation on overflow must not prevent closing the socket.
                with CancelScope(shield=True):
                    with move_on_after(SEND_TIMEOUT):
                        try:
                            await websocket.close(code=1013)
                        except Exception:
                            pass
            connection_scope.cancel()

    async def restore(self, websocket: WebSocket) -> None:
        """Called with lock held, after the first size report (or stdin)."""
        if self.closed or websocket in self._ready:
            return
        # Both backends feed complete decoded Unicode strings, exactly as sent
        # over JSON. Ghostty can therefore never retain an incomplete UTF-8
        # character, and its VT snapshot can safely be decoded as one string.
        try:
            snapshot = self.emulator.serialize().decode("utf-8")
        except GhosttyError:
            # A bounded continuation can overflow during a long control string.
            # Keep reading the PTY, then retry: reaching ground makes it valid.
            if websocket not in self._pending:
                log.warning("Deferring terminal restoration until its state can be serialized")
            self._pending.setdefault(websocket, current_time() + RESTORE_TIMEOUT)
            return
        # Keep one initial snapshot apart from the bounded live-output queue.
        # A long history must not overflow the queue before its sender can run.
        self._clients[websocket].snapshot = snapshot
        self._enqueue(websocket, "snapshot", None)
        self._pending.pop(websocket, None)
        self._ready.add(websocket)

    async def feed(self, text: str) -> None:
        async with self.lock:
            if self.closed:
                return
            self.emulator.feed(text)
            for websocket in list(self.websockets):
                try:
                    if websocket in self._ready:
                        self._enqueue(websocket, "stdout", text)
                    elif websocket in self._pending:
                        # This snapshot already includes text: do not send it twice.
                        await self.restore(websocket)
                except Exception:
                    self._detach(websocket)

    def resize(self, columns: int, rows: int) -> None:
        if not valid_size(columns, rows):
            raise ValueError("Terminal dimensions must be positive integers within limits")
        if not self.closed and self.emulator.size != (columns, rows):
            self.emulator.resize(columns, rows)

    def detach(self, websocket: WebSocket) -> None:
        client = self._clients.pop(websocket, None)
        if client is not None:
            client.snapshot = None
            client.send.close()
            client.scope.cancel()
        if websocket in self.websockets:
            self.websockets.remove(websocket)
        self._ready.discard(websocket)
        self._pending.pop(websocket, None)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.emulator.close()
        for client in self._clients.values():
            client.send.close()
            client.scope.cancel()
        self._ready.clear()
        self._pending.clear()
