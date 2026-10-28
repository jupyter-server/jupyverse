"""Keep terminal state independently of the attached WebSockets."""

from collections.abc import Callable
from typing import Any

import structlog
from anyio import Lock, move_on_after
from fastapi import WebSocket
from ghostty import GhosttyError, Terminal  # type: ignore[import-untyped]

log = structlog.get_logger()


class TerminalOutput:
    def __init__(self, detach: Callable[[WebSocket], None]):
        self.emulator = Terminal(cols=80, rows=24)
        self.lock = Lock()
        self.websockets: list[WebSocket] = []
        self._ready: set[WebSocket] = set()
        self._pending: set[WebSocket] = set()
        self._detach = detach
        self.closed = False

    async def setup(self, websocket: WebSocket) -> None:
        async with self.lock:
            if self.closed:
                return
            self.websockets.append(websocket)
            await websocket.send_json(["setup", {}])

    async def receive(self, websocket: WebSocket) -> Any:
        if websocket not in self._ready | self._pending:
            # JupyterLab sends a size when opening a widget, but an existing
            # widget may reconnect its socket without sending another size.
            with move_on_after(1):
                return await websocket.receive_json()
            async with self.lock:
                await self.restore(websocket)
        return await websocket.receive_json()

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
            self._pending.add(websocket)
            return
        await websocket.send_json(["stdout", snapshot])
        self._pending.discard(websocket)
        self._ready.add(websocket)

    async def feed(self, text: str) -> None:
        async with self.lock:
            if self.closed:
                return
            self.emulator.feed(text)
            for websocket in list(self.websockets):
                try:
                    if websocket in self._ready:
                        await websocket.send_json(["stdout", text])
                    elif websocket in self._pending:
                        # This snapshot already includes text: do not send it twice.
                        await self.restore(websocket)
                except Exception:
                    self._detach(websocket)

    def resize(self, columns: int, rows: int) -> None:
        if not self.closed and self.emulator.size != (columns, rows):
            self.emulator.resize(columns, rows)

    def detach(self, websocket: WebSocket) -> None:
        if websocket in self.websockets:
            self.websockets.remove(websocket)
        self._ready.discard(websocket)
        self._pending.discard(websocket)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.emulator.close()
        self._ready.clear()
        self._pending.clear()
