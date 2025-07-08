from __future__ import annotations

import json
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import cast

import anyio
from anyio import TASK_STATUS_IGNORED, create_task_group, open_process, sleep_forever
from anyio.abc import TaskStatus

from jupyverse_api.kernel import Kernel

from .connect import (
    cfg_t,
    connect_channel,
    read_connection_file,
)
from .connect import (
    write_connection_file as _write_connection_file,
)


@dataclass
class KernelSubprocess(Kernel):
    write_connection_file: bool
    kernelspec_path: str
    connection_file: str
    kernel_cwd: str | None
    capture_output: bool
    connection_cfg: cfg_t | None = None

    def __post_init__(self):
        super().__init__()

        if self.write_connection_file:
            self.connection_file, self.connection_cfg = _write_connection_file(self.connection_file)
        elif self.connection_file:
            self.connection_cfg = read_connection_file(self.connection_file)
        else:
            if self.connection_cfg is None:
                raise RuntimeError("No connection_cfg")
        self.key = cast(str, self.connection_cfg["key"])
        self.wait_for_ready = True

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        async with (
            create_task_group() as self.task_group,
            self._to_shell_send_stream,
            self._to_shell_receive_stream,
            self._from_shell_send_stream,
            self._from_shell_receive_stream,
            self._to_control_send_stream,
            self._to_control_receive_stream,
            self._from_control_send_stream,
            self._from_control_receive_stream,
            self._to_stdin_send_stream,
            self._to_stdin_receive_stream,
            self._from_stdin_send_stream,
            self._from_stdin_receive_stream,
            self._from_iopub_send_stream,
            self._from_iopub_receive_stream,
        ):
            with open(self.kernelspec_path) as f:
                kernelspec = json.load(f)
            cmd = [s.format(connection_file=self.connection_file) for s in kernelspec["argv"]]
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

            assert self.connection_cfg is not None
            identity = uuid.uuid4().hex.encode("ascii")
            self.shell_channel = connect_channel("shell", self.connection_cfg, identity=identity)
            self.stdin_channel = connect_channel("stdin", self.connection_cfg, identity=identity)
            self.control_channel = connect_channel(
                "control", self.connection_cfg, identity=identity
            )
            self.iopub_channel = connect_channel("iopub", self.connection_cfg)

            await self.task_group.start(self.shell_channel.start)
            await self.task_group.start(self.stdin_channel.start)
            await self.task_group.start(self.control_channel.start)
            await self.task_group.start(self.iopub_channel.start)

            self.task_group.start_soon(self.forward_messages_to_shell)
            self.task_group.start_soon(self.forward_messages_from_shell)
            self.task_group.start_soon(self.forward_messages_to_control)
            self.task_group.start_soon(self.forward_messages_from_control)
            self.task_group.start_soon(self.forward_messages_to_stdin)
            self.task_group.start_soon(self.forward_messages_from_stdin)
            self.task_group.start_soon(self.forward_messages_from_iopub)

            task_status.started()
            await sleep_forever()

    async def stop(self) -> None:
        try:
            self._process.terminate()
        except ProcessLookupError:
            pass
        await self._process.wait()
        if self.write_connection_file:
            path = anyio.Path(self.connection_file)
            await path.unlink(missing_ok=True)

        await self.shell_channel.stop()
        await self.stdin_channel.stop()
        await self.control_channel.stop()
        await self.iopub_channel.stop()
        self.task_group.cancel_scope.cancel()

    async def interrupt(self) -> None:
        self._process.send_signal(signal.SIGINT)

    async def forward_messages_to_shell(self) -> None:
        async for msg in self._to_shell_receive_stream:
            await self.shell_channel.asend_multipart(msg, copy=True).wait()

    async def forward_messages_from_shell(self) -> None:
        while True:
            msg = cast(list[bytes], await self.shell_channel.arecv_multipart(copy=True).wait())
            await self._from_shell_send_stream.send(msg)

    async def forward_messages_to_control(self) -> None:
        async for msg in self._to_control_receive_stream:
            await self.control_channel.asend_multipart(msg, copy=True).wait()

    async def forward_messages_from_control(self) -> None:
        while True:
            msg = cast(list[bytes], await self.control_channel.arecv_multipart(copy=True).wait())
            await self._from_control_send_stream.send(msg)

    async def forward_messages_to_stdin(self) -> None:
        async for msg in self._to_stdin_receive_stream:
            await self.stdin_channel.asend_multipart(msg, copy=True).wait()

    async def forward_messages_from_stdin(self) -> None:
        while True:
            msg = cast(list[bytes], await self.stdin_channel.arecv_multipart(copy=True).wait())
            await self._from_stdin_send_stream.send(msg)

    async def forward_messages_from_iopub(self) -> None:
        while True:
            msg = cast(list[bytes], await self.iopub_channel.arecv_multipart(copy=True).wait())
            await self._from_iopub_send_stream.send(msg)
