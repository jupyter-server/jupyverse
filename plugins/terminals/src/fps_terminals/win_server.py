import os
import signal
from functools import partial

from anyio import to_thread
from winpty import PTY, WinptyError  # type: ignore

from .base import BaseTerminalServer


def open_terminal(command=None, columns=80, lines=24):
    if command is None:
        command = os.environ.get("COMSPEC") or "cmd.exe"
    env = "\0".join([f"{k}={v}" for k, v in os.environ.items()]) + "\0"
    process = PTY(columns, lines)
    process.spawn(command, env=env)
    return process


class _TerminalServer(BaseTerminalServer):
    """A Windows shell which outlives the websockets attached to it."""

    _pty_errors = (WinptyError,)

    def __init__(self) -> None:
        super().__init__()
        self.process = open_terminal()

    def _write(self, text: str) -> None:
        self.process.write(text)

    def _set_size(self, columns: int, rows: int) -> None:
        self.process.set_size(columns, rows)

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
                    await self.output.feed(data)
        finally:
            try:
                self.quit()
            finally:
                # A cancelled worker retains its bound PTY until read() returns.
                self.process = None

    def _shutdown(self) -> None:
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
                if self.process.isalive():
                    raise
