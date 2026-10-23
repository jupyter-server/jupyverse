import os
import signal
from collections.abc import Awaitable, Callable
from functools import partial

import structlog
from anyio import TASK_STATUS_IGNORED, CancelScope, create_task_group, to_thread
from anyio.abc import TaskStatus
from fastapi import WebSocket, WebSocketDisconnect
from jupyverse_terminals import TerminalServer
from winpty import PTY, WinptyError  # type: ignore

log = structlog.get_logger()


def open_terminal(command=None, columns=80, lines=24):
    if command is None:
        command = os.environ.get("COMSPEC") or "cmd.exe"
    env = "\0".join([f"{k}={v}" for k, v in os.environ.items()]) + "\0"
    process = PTY(columns, lines)
    process.spawn(command, env=env)
    return process


class _TerminalServer(TerminalServer):
    """A Windows shell which outlives the websockets attached to it."""

    def __init__(self) -> None:
        self.process = open_terminal()
        self.websockets: list[WebSocket] = []
        self.sizes: dict[WebSocket, tuple[int, int]] = {}
        self.closed = False
        self.read_scope = CancelScope()

    async def serve(self, websocket: WebSocket, permissions) -> None:
        if self.closed:
            return
        self.websockets.append(websocket)
        can_execute = permissions is None or "execute" in permissions.get("terminals", [])
        try:
            await websocket.send_json(["setup", {}])
            while True:
                msg = await websocket.receive_json()
                if can_execute and not self.closed:
                    if msg[0] == "stdin":
                        self.process.write(msg[1])
                    elif msg[0] == "set_size":
                        rows, columns = msg[1:3]
                        if 0 < rows <= 65535 and 0 < columns <= 65535:
                            self.sizes[websocket] = (rows, columns)
                            self._resize()
        except (WebSocketDisconnect, WinptyError):
            pass
        finally:
            self.quit(websocket)

    def _start_soon(self, func: Callable[[], Awaitable[None]]) -> None:
        self.task_group.start_soon(self._isolated, func)

    async def _isolated(self, func: Callable[[], Awaitable[None]]) -> None:
        try:
            await func()
        except Exception:
            log.exception("Terminal task failed")

    async def run(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        async with create_task_group() as self.task_group:
            task_status.started()
            await self._run()

    async def _run(self) -> None:
        try:
            with self.read_scope:
                while not self.closed:
                    try:
                        data = await to_thread.run_sync(
                            partial(self.process.read, blocking=True),
                            abandon_on_cancel=True,
                        )
                    except WinptyError:
                        if self.closed or not self.process.isalive():
                            break
                        raise
                    if not data:
                        break
                    for websocket in list(self.websockets):
                        try:
                            await websocket.send_json(["stdout", data])
                        except Exception:
                            self.quit(websocket)
        finally:
            try:
                self.quit()
            finally:
                # A cancelled worker retains its bound PTY until read() returns.
                self.process = None

    def _resize(self) -> None:
        if self.closed or not self.sizes:
            return
        rows = min(size[0] for size in self.sizes.values())
        columns = min(size[1] for size in self.sizes.values())
        self.process.set_size(columns, rows)

    async def _close_websockets(self) -> None:
        for websocket in list(self.websockets):
            try:
                await websocket.send_json(["disconnect", 1])
                await websocket.close()
            except Exception:
                pass
        self.websockets.clear()
        self.sizes.clear()

    def quit(self, websocket: WebSocket | None = None) -> None:
        if websocket is not None:
            if websocket in self.websockets:
                self.websockets.remove(websocket)
            if self.sizes.pop(websocket, None) is not None:
                try:
                    self._resize()
                except WinptyError:
                    pass
            return
        if self.closed:
            return
        self.closed = True
        self.read_scope.cancel()
        try:
            if self.process.isalive() and self.process.pid is not None:
                # On Windows SIGTERM uses TerminateProcess, not a catchable signal.
                try:
                    os.kill(self.process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        finally:
            try:
                # Wake a blocking read even if terminating the shell did not
                # close its output pipe. Also used after task cancellation.
                self.process.cancel_io()
            except WinptyError:
                # A naturally exited shell may have no pending I/O to cancel.
                # Let the disconnect notification run instead of cancelling it.
                if self.process.isalive():
                    raise
            finally:
                self._start_soon(self._close_websockets)
