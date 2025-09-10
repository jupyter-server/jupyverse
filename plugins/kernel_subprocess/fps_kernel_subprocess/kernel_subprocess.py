from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import uuid
from dataclasses import dataclass
from typing import cast

import anyio
from anyio import TASK_STATUS_IGNORED, create_task_group, open_file, open_process, to_thread
from anyio.abc import TaskStatus

from jupyverse_api.environments import Environments
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
    environments: Environments
    connection_cfg: cfg_t | None = None
    environment_id: str = ""

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
        self._process = None
        self._pid = None

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        async with (
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
            create_task_group() as self.task_group,
        ):
            async with await open_file(self.kernelspec_path) as f:
                contents = await f.read()
            kernelspec = json.loads(contents)
            launch_kernel_cmd = [
                s.format(connection_file=self.connection_file) for s in kernelspec["argv"]
            ]
            if self.capture_output:
                stdout = subprocess.DEVNULL
                stderr = subprocess.STDOUT
            else:
                stdout = None
                stderr = None
            kernel_cwd = self.kernel_cwd if self.kernel_cwd else None
            if self.environment_id:
                cmd = " ".join(launch_kernel_cmd)
                self._pid = await self.environments.run_in_environment(self.environment_id, cmd)
            else:
                if launch_kernel_cmd and launch_kernel_cmd[0] in {
                    "python",
                    f"python{sys.version_info[0]}",
                    "python" + ".".join(map(str, sys.version_info[:2])),
                }:
                    launch_kernel_cmd[0] = sys.executable
                self._process = await open_process(
                    launch_kernel_cmd, stdout=stdout, stderr=stderr, cwd=kernel_cwd
                )

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
            self.started.set()

    async def stop(self) -> None:
        if self._process:
            try:
                self._process.terminate()
            except ProcessLookupError:
                pass
            await self._process.wait()
            if self.write_connection_file:
                path = anyio.Path(self.connection_file)
                await path.unlink(missing_ok=True)
        else:
            try:
                os.kill(self._pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                await to_thread.run_sync(os.waitpid, self._pid, 0)
            except ChildProcessError:
                pass

        await self.shell_channel.stop()
        await self.stdin_channel.stop()
        await self.control_channel.stop()
        await self.iopub_channel.stop()
        self.task_group.cancel_scope.cancel()

    async def interrupt(self) -> None:
        if self._process:
            self._process.send_signal(signal.SIGINT)
        else:
            os.kill(self._pid, signal.SIGINT)

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
