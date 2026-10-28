import codecs
import fcntl
import os
import pty
import signal
import struct
import termios

import structlog
from anyio import (
    TASK_STATUS_IGNORED,
    CancelScope,
    CapacityLimiter,
    Event,
    create_task_group,
    move_on_after,
    to_thread,
    wait_readable,
)
from anyio.abc import TaskStatus

from .base import BaseTerminalServer

log = structlog.get_logger()


class _TerminalServer(BaseTerminalServer):
    """A shell in a PTY, which outlives the websockets attached to it."""

    def __init__(self) -> None:
        super().__init__()
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
        self.log = log.bind(pid=pid)

    def _write(self, text: str) -> None:
        self.p_out.write(text.encode())

    def _set_size(self, columns: int, rows: int) -> None:
        winsize = struct.pack("HH", rows, columns)
        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)

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
            await self.output.feed(text)

    def _shutdown(self) -> None:
        try:
            try:
                os.kill(self.pid, signal.SIGHUP)
            except ProcessLookupError:
                pass
        finally:
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
