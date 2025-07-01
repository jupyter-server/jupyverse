from __future__ import annotations

import json
import signal
import subprocess
import sys
from dataclasses import dataclass

import anyio
from anyio import open_process

from jupyverse_api.kernel import Kernel


@dataclass
class KernelSubprocess(Kernel):
    write_connection_file: bool
    kernelspec_path: str
    connection_file_path: str
    kernel_cwd: str | None
    capture_output: bool

    async def start(self) -> None:
        with open(self.kernelspec_path) as f:
            kernelspec = json.load(f)
        cmd = [s.format(connection_file=self.connection_file_path) for s in kernelspec["argv"]]
        if cmd and cmd[0] in {
            "python",
            f"python{sys.version_info[0]}",
            "python" + ".".join(map(str, sys.version_info[:2])),
        }:
            cmd[0] = sys.executable
        if self.capture_output:
            stdout = subprocess.DEVNULL
            stderr = subprocess.STDOUT
        else:
            stdout = None
            stderr = None
        kernel_cwd = self.kernel_cwd if self.kernel_cwd else None
        self._process = await open_process(cmd, stdout=stdout, stderr=stderr, cwd=kernel_cwd)

    async def interrupt(self) -> None:
        self._process.send_signal(signal.SIGINT)

    async def stop(self) -> None:
        try:
            self._process.terminate()
        except ProcessLookupError:
            pass
        await self._process.wait()
        if self.write_connection_file:
            path = anyio.Path(self.connection_file_path)
            try:
                await path.unlink()
            except Exception:
                pass
