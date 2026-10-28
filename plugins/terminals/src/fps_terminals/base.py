"""Session handling shared by the POSIX and Windows terminal backends."""

from abc import abstractmethod
from collections.abc import Awaitable, Callable

import structlog
from anyio import TASK_STATUS_IGNORED, CancelScope, create_task_group
from anyio.abc import TaskStatus
from fastapi import WebSocket, WebSocketDisconnect
from jupyverse_terminals import TerminalServer

from .output import TerminalOutput, valid_size

log = structlog.get_logger()


class BaseTerminalServer(TerminalServer):
    _pty_errors: tuple[type[Exception], ...] = (OSError,)

    def __init__(self) -> None:
        self.output = TerminalOutput(self.quit)
        self.websockets = self.output.websockets
        self.sizes: dict[WebSocket, tuple[int, int]] = {}
        self.closed = False
        self.read_scope = CancelScope()
        self.log = log

    async def serve(self, websocket: WebSocket, permissions) -> None:
        if self.closed:
            return
        can_execute = permissions is None or "execute" in permissions.get("terminals", [])
        async with create_task_group() as tasks:
            try:
                await self.output.setup(websocket)
                await tasks.start(self.output.send, websocket, tasks.cancel_scope)
                while True:
                    msg = await self.output.receive(websocket)
                    async with self.output.lock:
                        # Once closed, the PTY may already be released or reused.
                        if self.closed:
                            return
                        if msg[0] == "set_size":
                            rows, columns = msg[1:3]
                            if valid_size(columns, rows):
                                if can_execute:
                                    self.sizes[websocket] = (rows, columns)
                                    self._resize()
                                await self.output.restore(websocket)
                        elif msg[0] == "stdin" and can_execute:
                            # Non-JupyterLab clients may send input without a size.
                            await self.output.restore(websocket)
                            self._write(msg[1])
            except WebSocketDisconnect:
                pass
            except self._pty_errors:
                pass
            finally:
                self.quit(websocket)
                tasks.cancel_scope.cancel()

    def _resize(self) -> None:
        # Unreported sizes do not constrain the PTY. Keep the last size when
        # no clients remain, minimizing each dimension independently.
        if self.closed or not self.sizes:
            return
        rows = min(size[0] for size in self.sizes.values())
        columns = min(size[1] for size in self.sizes.values())
        self._set_size(columns, rows)
        self.output.resize(columns, rows)

    def _start_soon(self, func: Callable[[], Awaitable[None]]) -> None:
        self.task_group.start_soon(self._isolated, func)

    async def _isolated(self, func: Callable[[], Awaitable[None]]) -> None:
        try:
            await func()
        except Exception:
            self.log.exception("Terminal task failed")

    async def run(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        async with create_task_group() as self.task_group:
            task_status.started()
            try:
                await self._run()
            finally:
                self.output.close()

    async def _close_websockets(self) -> None:
        self.output.close()
        await self.output.wait_closed()
        self.sizes.clear()

    def quit(self, websocket: WebSocket | None = None) -> None:
        if websocket is not None:
            self.output.detach(websocket)
            if self.sizes.pop(websocket, None) is not None:
                try:
                    self._resize()
                except self._pty_errors:
                    # The shell may have exited while the client disconnected.
                    pass
            return
        if self.closed:
            return
        self.closed = True
        self.read_scope.cancel()
        try:
            self._shutdown()
        finally:
            self._start_soon(self._close_websockets)

    @abstractmethod
    def _write(self, text: str) -> None: ...

    @abstractmethod
    def _set_size(self, columns: int, rows: int) -> None: ...

    @abstractmethod
    def _shutdown(self) -> None: ...

    @abstractmethod
    async def _run(self) -> None: ...
