import codecs
import fcntl
import os
import pty
import signal
import struct
import termios
from collections.abc import Awaitable, Callable

import structlog
from anyio import (
    TASK_STATUS_IGNORED,
    CancelScope,
    CapacityLimiter,
    Event,
    Lock,
    create_task_group,
    move_on_after,
    to_thread,
    wait_readable,
)
from anyio.abc import TaskStatus
from fastapi import WebSocket, WebSocketDisconnect
from jupyverse_terminals import TerminalServer

log = structlog.get_logger()

# Recent output replayed to a new websocket, in characters.
HISTORY_SIZE = 65536
# Home, clear the screen and the scrollback: the replay replaces what the
# client shows, as JupyterLab keeps it when it reconnects on its own.
CLEAR_SCREEN = "\x1b[H\x1b[2J\x1b[3J"
# Sent in pieces, as JSON escapes can make the whole replay too big for a
# client's message size limit.
REPLAY_CHUNK = 8192


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
        # Replayed to a new websocket so it does not start blank.
        self.history = ""
        # Keeps the replay ahead of the live output on a new websocket.
        self.output_lock = Lock()

    async def serve(self, websocket: WebSocket, permissions) -> None:
        if self.closed:
            return
        can_execute = permissions is None or "execute" in permissions.get("terminals", [])
        try:
            await websocket.send_json(["setup", {}])
            async with self.output_lock:
                # The terminal may have closed while waiting for the lock.
                if self.closed:
                    await websocket.send_json(["disconnect", 1])
                    return
                self.websockets.append(websocket)
                if self.history:
                    replay = CLEAR_SCREEN + self.history
                    for start in range(0, len(replay), REPLAY_CHUNK):
                        chunk = replay[start : start + REPLAY_CHUNK]
                        await websocket.send_json(["stdout", chunk])
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
            async with self.output_lock:
                if text:
                    self._record(text)
                for websocket in list(self.websockets):
                    try:
                        await websocket.send_json(["stdout", text])
                    except Exception:
                        self.quit(websocket)

    def _record(self, text: str) -> None:
        # Bounded in characters, not reads: a prompt redrawn on each resize
        # must not push the older output out.
        history = self.history + text
        if len(history) > HISTORY_SIZE:
            history = history[-HISTORY_SIZE:]
            # Start on a line, not in the middle of one or of an escape sequence.
            newline = history.find("\n")
            if newline != -1:
                history = history[newline + 1 :]
        self.history = history

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
        exited = Event()
        async with create_task_group() as tasks:
            # Start exactly one waiter, even if shutdown has already cancelled us.
            with CancelScope(shield=True):
                waiter_scope = await tasks.start(self._wait_for_child, exited)
            try:
                try:
                    await self._wait_exit(exited, 5)
                finally:
                    if not exited.is_set():
                        try:
                            os.kill(self.pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass
                        # Collect the child even during shutdown cancellation.
                        with CancelScope(shield=True):
                            if not await self._wait_exit(exited, 5):
                                log.warning("Terminal shell did not exit", pid=self.pid)
            finally:
                # If the child is stuck, stop awaiting the worker. Its single
                # blocking waitpid() still reaps the child if it eventually exits.
                waiter_scope.cancel()

    async def _wait_for_child(
        self, exited: Event, *, task_status: TaskStatus[CancelScope] = TASK_STATUS_IGNORED
    ) -> None:
        with CancelScope(shield=True) as scope:
            task_status.started(scope)
            # A separate limiter keeps unrelated blocked worker calls from
            # preventing this terminal's reaper from starting.
            await to_thread.run_sync(
                self._waitpid, abandon_on_cancel=True, limiter=CapacityLimiter(1)
            )
            exited.set()

    def _waitpid(self) -> None:
        try:
            os.waitpid(self.pid, 0)
        except ChildProcessError:
            pass

    async def _wait_exit(self, exited: Event, timeout: float) -> bool:
        with move_on_after(timeout):
            await exited.wait()
        return exited.is_set()
