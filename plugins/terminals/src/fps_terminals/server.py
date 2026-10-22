import codecs
import fcntl
import os
import pty
import signal
import struct
import termios
from collections.abc import Awaitable, Callable

import structlog
from anyio import TASK_STATUS_IGNORED, CancelScope, create_task_group, sleep, wait_readable
from anyio.abc import TaskStatus
from fastapi import WebSocket, WebSocketDisconnect
from jupyverse_terminals import TerminalServer

log = structlog.get_logger()


class _TerminalServer(TerminalServer):
    """A shell in a PTY, which outlives the websockets attached to it."""

    def __init__(self) -> None:
        # FIXME: pass in config
        command = os.environ.get("SHELL") or "/bin/sh"
        columns = 80
        lines = 24

        pid, fd = pty.fork()
        if pid == 0:
            argv = [command]
            env = os.environ.copy()
            env.update(TERM="linux", COLUMNS=str(columns), LINES=str(lines))
            os.execvpe(argv[0], argv, env)
        self.pid = pid
        self.fd = fd
        self.p_out = os.fdopen(self.fd, "w+b", 0)
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
                # Once closed, self.fd may already be reused by another file.
                if can_execute and not self.closed:
                    if msg[0] == "stdin":
                        self.p_out.write(msg[1].encode())
                    elif msg[0] == "set_size":
                        rows, columns = msg[1:3]
                        if 0 < rows <= 65535 and 0 < columns <= 65535:
                            self.sizes[websocket] = (rows, columns)
                            self._resize()
        except (WebSocketDisconnect, OSError):
            pass
        finally:
            self.quit(websocket)

    def _start_soon(self, func: Callable[[], Awaitable[None]]) -> None:
        self.task_group.start_soon(self._isolated, func)

    def _resize(self) -> None:
        # Clients that have not reported a size do not constrain the PTY.
        # Keep the last size when no clients remain.
        if self.closed or not self.sizes:
            return
        rows = min(size[0] for size in self.sizes.values())
        columns = min(size[1] for size in self.sizes.values())
        winsize = struct.pack("HH", rows, columns)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

    async def _isolated(self, func: Callable[[], Awaitable[None]]) -> None:
        # The task group is shared by all terminals: a failure stays in this one.
        try:
            await func()
        except Exception:
            log.exception("Terminal task failed", pid=self.pid)

    async def run(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        async with create_task_group() as self.task_group:
            task_status.started()
            await self._run()

    async def _run(self) -> None:
        decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
        try:
            with self.read_scope:
                await self._read(decoder)
        finally:
            # Not in quit(): wait_readable() may still be watching the fd.
            try:
                self.p_out.close()
            except Exception:
                pass
            self.quit()

    async def _read(self, decoder: codecs.IncrementalDecoder) -> None:
        while True:
            await wait_readable(self.p_out)
            try:
                data = self.p_out.read(65536)
            except OSError:
                # EIO: the shell exited.
                return
            if not data:
                return
            text = decoder.decode(data)
            for websocket in list(self.websockets):
                try:
                    await websocket.send_json(["stdout", text])
                except Exception:
                    self.quit(websocket)

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
                except OSError:
                    # The shell may have exited while the client disconnected.
                    pass
            return
        if self.closed:
            return
        self.closed = True
        self.read_scope.cancel()
        try:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        finally:
            self._start_soon(self._close_websockets)
            self._start_soon(self._reap)

    async def _reap(self) -> None:
        # Avoid a zombie; SIGKILL a shell that ignores SIGHUP.
        exited = False
        try:
            exited = await self._wait_exit(5)
        finally:
            # Also when cancelled: at server shutdown, fps cancels the task
            # group well before the 5 seconds are up.
            if not exited:
                try:
                    os.kill(self.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                # Reap even during shutdown cancellation. Keep the wait bounded
                # for a process stuck in uninterruptible I/O.
                with CancelScope(shield=True):
                    if not await self._wait_exit(5):
                        log.warning("Terminal shell did not exit", pid=self.pid)

    async def _wait_exit(self, timeout: float) -> bool:
        for _ in range(int(timeout * 10)):
            try:
                pid, _ = os.waitpid(self.pid, os.WNOHANG)
            except ChildProcessError:
                return True
            if pid:
                return True
            await sleep(0.1)
        return False
