from __future__ import annotations

import time
import uuid
from typing import Any

from anyio import (
    TASK_STATUS_IGNORED,
    Event,
    create_memory_object_stream,
    create_task_group,
    fail_after,
    move_on_after,
)
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.stapled import StapledObjectStream
from pycrdt import Array, Map, Text

from jupyverse_api.kernel import DefaultKernelFactory, Kernel
from jupyverse_api.yjs import Yjs

from .kernelspec import find_kernelspec
from .message import create_message, deserialize_message, feed_identities, serialize_message


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.time())


class KernelDriver:
    task_group: TaskGroup

    def __init__(
        self,
        default_kernel_factory: DefaultKernelFactory,
        kernel_name: str = "",
        kernelspec_path: str = "",
        kernel_cwd: str = "",
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
        yjs: Yjs | None = None,
    ) -> None:
        kernelspec_path = kernelspec_path or find_kernelspec(kernel_name)
        self.yjs = yjs
        if not kernelspec_path:
            raise RuntimeError("Could not find a kernel, maybe you forgot to install one?")
        self.kernel = default_kernel_factory(
            write_connection_file,
            kernelspec_path,
            connection_file,
            kernel_cwd,
            capture_kernel_output,
        )
        self.session_id = uuid.uuid4().hex
        self.msg_cnt = 0
        self.execute_requests: dict[str, dict[str, StapledObjectStream]] = {}
        self.comm_messages: StapledObjectStream = StapledObjectStream(
            *create_memory_object_stream[dict](max_buffer_size=1024)
        )
        self.stopped_event = Event()

    async def restart(self, startup_timeout: float = float("inf")) -> None:
        self.task_group.cancel_scope.cancel()
        await self.stopped_event.wait()
        self.stopped_event = Event()
        async with create_task_group() as tg:
            self.task_group = tg
            msg = create_message("shutdown_request", content={"restart": True})
            msg_ser = serialize_message(msg, self.kernel.key, change_date_to_str=True)
            await self.kernel.control_stream.send(msg_ser)
            while True:
                msg_ser = await self.kernel.control_stream.receive()
                idents, msg_list = feed_identities(msg_ser)
                msg = deserialize_message(msg_list, change_str_to_date=True)
                if msg["msg_type"] == "shutdown_reply" and msg["content"]["restart"]:
                    break
            await self._wait_for_ready(startup_timeout)
            self.listen_channels()
            tg.start_soon(self._handle_comms)

    async def start(
        self,
        startup_timeout: float = float("inf"),
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
    ) -> None:
        async with create_task_group() as tg:
            self.task_group = tg
            await tg.start(self.kernel.start)
            await self._wait_for_ready(startup_timeout)
            self.listen_channels()
            self.task_group.start_soon(self._handle_comms)
            task_status.started()
        self.stopped_event.set()

    def listen_channels(self):
        self.task_group.start_soon(self.listen_iopub)
        self.task_group.start_soon(self.listen_shell)

    async def stop(self) -> None:
        await self.kernel.stop()
        self.task_group.cancel_scope.cancel()

    async def listen_iopub(self):
        while True:
            msg_ser = await self.kernel.iopub_stream.receive()
            idents, msg_list = feed_identities(msg_ser)
            msg = deserialize_message(msg_list, change_str_to_date=True)
            parent_id = msg["parent_header"].get("msg_id")
            if msg["msg_type"] in ("comm_open", "comm_msg"):
                await self.comm_messages.send(msg)
            elif parent_id in self.execute_requests.keys():
                await self.execute_requests[parent_id]["iopub_msg"].send(msg)

    async def listen_shell(self):
        while True:
            msg_ser = await self.kernel.shell_stream.receive()
            idents, msg_list = feed_identities(msg_ser)
            msg = deserialize_message(msg_list, change_str_to_date=True)
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests.keys():
                await self.execute_requests[msg_id]["shell_msg"].send(msg)

    async def execute(
        self,
        ycell: Map,
        timeout: float = float("inf"),
        msg_id: str = "",
        wait_for_executed: bool = True,
    ) -> None:
        if ycell["cell_type"] != "code":
            return
        ycell["execution_state"] = "busy"
        content = {"code": str(ycell["source"]), "silent": False}
        msg = create_message(
            "execute_request", content, session_id=self.session_id, msg_id=str(self.msg_cnt)
        )
        if msg_id:
            msg["header"]["msg_id"] = msg_id
        else:
            msg_id = msg["header"]["msg_id"]
        self.msg_cnt += 1
        msg_ser = serialize_message(msg, self.kernel.key, change_date_to_str=True)
        await self.kernel.shell_stream.send(msg_ser)
        self.execute_requests[msg_id] = {
            "iopub_msg": StapledObjectStream(
                *create_memory_object_stream[dict](max_buffer_size=1024)
            ),
            "shell_msg": StapledObjectStream(
                *create_memory_object_stream[dict](max_buffer_size=1024)
            ),
        }
        if wait_for_executed:
            deadline = time.time() + timeout
            while True:
                try:
                    with fail_after(deadline_to_timeout(deadline)):
                        msg = await self.execute_requests[msg_id]["iopub_msg"].receive()
                except TimeoutError:
                    error_message = f"Kernel didn't respond in {timeout} seconds"
                    raise RuntimeError(error_message)
                await self._handle_outputs(ycell["outputs"], msg)
                if (
                    msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle"
                ):
                    break
            try:
                with fail_after(deadline_to_timeout(deadline)):
                    msg = await self.execute_requests[msg_id]["shell_msg"].receive()
            except TimeoutError:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            with ycell.doc.transaction():
                ycell["execution_count"] = msg["content"]["execution_count"]
                ycell["execution_state"] = "idle"
            del self.execute_requests[msg_id]
        else:
            self.task_group.start_soon(lambda: self._handle_iopub(msg_id, ycell))

    async def _handle_iopub(self, msg_id: str, ycell: Map) -> None:
        while True:
            msg = await self.execute_requests[msg_id]["iopub_msg"].receive()
            await self._handle_outputs(ycell["outputs"], msg)
            if (
                msg["header"]["msg_type"] == "status"
                and msg["content"]["execution_state"] == "idle"
            ):
                msg = await self.execute_requests[msg_id]["shell_msg"].receive()
                with ycell.doc.transaction():
                    ycell["execution_count"] = msg["content"]["execution_count"]
                    ycell["execution_state"] = "idle"
                break

    async def _handle_comms(self) -> None:
        if self.yjs is None or self.yjs.widgets is None:  # type: ignore
            return

        while True:
            msg = await self.comm_messages.receive()
            msg_type = msg["header"]["msg_type"]
            if msg_type == "comm_open":
                comm_id = msg["content"]["comm_id"]
                comm = Comm(comm_id, self.session_id, self.kernel, self.task_group)
                self.yjs.widgets.comm_open(msg, comm)  # type: ignore
            elif msg_type == "comm_msg":
                self.yjs.widgets.comm_msg(msg)  # type: ignore

    async def _wait_for_ready(self, timeout):
        deadline = time.time() + timeout
        new_timeout = timeout
        while True:
            msg = create_message(
                "kernel_info_request", session_id=self.session_id, msg_id=str(self.msg_cnt)
            )
            self.msg_cnt += 1
            msg_ser = serialize_message(msg, self.kernel.key, change_date_to_str=True)
            await self.kernel.shell_stream.send(msg_ser)
            try:
                with fail_after(new_timeout):
                    msg_ser = await self.kernel.shell_stream.receive()
                    idents, msg_list = feed_identities(msg_ser)
                    msg = deserialize_message(msg_list, change_str_to_date=True)
            except TimeoutError:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            if msg["msg_type"] == "kernel_info_reply":
                with move_on_after(0.2):
                    msg_ser = await self.kernel.iopub_stream.receive()
                    idents, msg_list = feed_identities(msg_ser)
                    msg = deserialize_message(msg_list, change_str_to_date=True)
                    return
            new_timeout = deadline_to_timeout(deadline)

    async def _handle_outputs(self, outputs: Array, msg: dict[str, Any]):
        msg_type = msg["header"]["msg_type"]
        content = msg["content"]
        if msg_type == "stream":
            with outputs.doc.transaction():
                if (not outputs) or (outputs[-1]["name"] != content["name"]):  # type: ignore
                    outputs.append(
                        Map(
                            {
                                "name": content["name"],
                                "output_type": msg_type,
                                "text": Text(content["text"]),
                            }
                        )
                    )
                else:
                    text = outputs[-1]["text"]
                    text += content["text"]  # type: ignore
        elif msg_type in ("display_data", "execute_result"):
            if "application/vnd.jupyter.ywidget-view+json" in content["data"]:
                # this is a collaborative widget
                model_id = content["data"]["application/vnd.jupyter.ywidget-view+json"]["model_id"]
                if self.yjs is not None and self.yjs.widgets is not None:  # type: ignore
                    if model_id in self.yjs.widgets.widgets:  # type: ignore
                        doc = self.yjs.widgets.widgets[model_id]["model"].ydoc  # type: ignore
                        path = f"ywidget:{doc.guid}"
                        await self.yjs.room_manager.websocket_server.get_room(path, ydoc=doc)  # type: ignore
                        outputs.append(doc)
            else:
                output = {
                    "data": content["data"],
                    "metadata": {},
                    "output_type": msg_type,
                }
                if msg_type == "execute_result":
                    output["execution_count"] = content["execution_count"]
                outputs.append(output)
        elif msg_type == "error":
            outputs.append(
                {
                    "ename": content["ename"],
                    "evalue": content["evalue"],
                    "output_type": "error",
                    "traceback": content["traceback"],
                }
            )


class Comm:
    def __init__(self, comm_id: str, session_id: str, kernel: Kernel, task_group: TaskGroup):
        self.comm_id = comm_id
        self.session_id = session_id
        self.kernel = kernel
        self.task_group = task_group
        self.msg_cnt = 0

    def send(self, buffers):
        msg = create_message(
            "comm_msg",
            content={"comm_id": self.comm_id},
            session_id=self.session_id,
            msg_id=self.msg_cnt,
            buffers=buffers,
        )
        self.msg_cnt += 1

        self.task_group.start_soon(self.send_message, msg)

    async def send_message(self, msg):
        msg_ser = serialize_message(msg, self.kernel.key, change_date_to_str=True)
        await self.kernel.shell_stream.send(msg_ser)
