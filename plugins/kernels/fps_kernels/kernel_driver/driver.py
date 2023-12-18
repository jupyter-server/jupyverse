import asyncio
import os
import time
import uuid
from typing import Any, Dict, List, Optional, cast

from pycrdt import Array, Map

from jupyverse_api.yjs import Yjs

from .connect import cfg_t, connect_channel, launch_kernel, read_connection_file
from .connect import write_connection_file as _write_connection_file
from .kernelspec import find_kernelspec
from .message import create_message, receive_message, send_message


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.time())


class KernelDriver:
    def __init__(
        self,
        kernel_name: str = "",
        kernelspec_path: str = "",
        kernel_cwd: str = "",
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
        yjs: Optional[Yjs] = None,
    ) -> None:
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path or find_kernelspec(kernel_name)
        self.kernel_cwd = kernel_cwd
        self.yjs = yjs
        if not self.kernelspec_path:
            raise RuntimeError("Could not find a kernel, maybe you forgot to install one?")
        if write_connection_file:
            self.connection_file_path, self.connection_cfg = _write_connection_file(connection_file)
        else:
            self.connection_file_path = connection_file
            self.connection_cfg = read_connection_file(connection_file)
        self.key = cast(str, self.connection_cfg["key"])
        self.session_id = uuid.uuid4().hex
        self.msg_cnt = 0
        self.execute_requests: Dict[str, Dict[str, asyncio.Queue]] = {}
        self.comm_messages: asyncio.Queue = asyncio.Queue()
        self.tasks: List[asyncio.Task] = []

    async def restart(self, startup_timeout: float = float("inf")) -> None:
        for task in self.tasks:
            task.cancel()
        msg = create_message("shutdown_request", content={"restart": True})
        await send_message(msg, self.control_channel, self.key, change_date_to_str=True)
        while True:
            msg = cast(
                Dict[str, Any], await receive_message(self.control_channel, change_str_to_date=True)
            )
            if msg["msg_type"] == "shutdown_reply" and msg["content"]["restart"]:
                break
        await self._wait_for_ready(startup_timeout)
        self.tasks = []
        self.listen_channels()

    async def start(self, startup_timeout: float = float("inf"), connect: bool = True) -> None:
        self.kernel_process = await launch_kernel(
            self.kernelspec_path,
            self.connection_file_path,
            self.kernel_cwd,
            self.capture_kernel_output,
        )
        if connect:
            await self.connect(startup_timeout)

    async def connect(self, startup_timeout: float = float("inf")) -> None:
        self.connect_channels()
        await self._wait_for_ready(startup_timeout)
        self.listen_channels()
        self.tasks.append(asyncio.create_task(self._handle_comms()))

    def connect_channels(self, connection_cfg: Optional[cfg_t] = None):
        connection_cfg = connection_cfg or self.connection_cfg
        self.shell_channel = connect_channel("shell", connection_cfg)
        self.control_channel = connect_channel("control", connection_cfg)
        self.iopub_channel = connect_channel("iopub", connection_cfg)

    def listen_channels(self):
        self.tasks.append(asyncio.create_task(self.listen_iopub()))
        self.tasks.append(asyncio.create_task(self.listen_shell()))

    async def stop(self) -> None:
        self.kernel_process.kill()
        await self.kernel_process.wait()
        os.remove(self.connection_file_path)
        for task in self.tasks:
            task.cancel()

    async def listen_iopub(self):
        while True:
            msg = await receive_message(self.iopub_channel, change_str_to_date=True)
            parent_id = msg["parent_header"].get("msg_id")
            if msg["msg_type"] in ("comm_open", "comm_msg"):
                self.comm_messages.put_nowait(msg)
            elif parent_id in self.execute_requests.keys():
                self.execute_requests[parent_id]["iopub_msg"].put_nowait(msg)

    async def listen_shell(self):
        while True:
            msg = await receive_message(self.shell_channel, change_str_to_date=True)
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests.keys():
                self.execute_requests[msg_id]["shell_msg"].put_nowait(msg)

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
        await send_message(msg, self.shell_channel, self.key, change_date_to_str=True)
        self.execute_requests[msg_id] = {
            "iopub_msg": asyncio.Queue(),
            "shell_msg": asyncio.Queue(),
        }
        if wait_for_executed:
            deadline = time.time() + timeout
            while True:
                try:
                    msg = await asyncio.wait_for(
                        self.execute_requests[msg_id]["iopub_msg"].get(),
                        deadline_to_timeout(deadline),
                    )
                except asyncio.TimeoutError:
                    error_message = f"Kernel didn't respond in {timeout} seconds"
                    raise RuntimeError(error_message)
                await self._handle_outputs(ycell["outputs"], msg)
                if (
                    (msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle")
                ):
                    break
            try:
                msg = await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell_msg"].get(),
                    deadline_to_timeout(deadline),
                )
            except asyncio.TimeoutError:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            with ycell.doc.transaction():
                ycell["execution_count"] = msg["content"]["execution_count"]
                ycell["execution_state"] = "idle"
            del self.execute_requests[msg_id]
        else:
            self.tasks.append(asyncio.create_task(self._handle_iopub(msg_id, ycell)))

    async def _handle_iopub(self, msg_id: str, ycell: Map) -> None:
        while True:
            msg = await self.execute_requests[msg_id]["iopub_msg"].get()
            await self._handle_outputs(ycell["outputs"], msg)
            if (
                (msg["header"]["msg_type"] == "status"
                and msg["content"]["execution_state"] == "idle")
            ):
                msg = await self.execute_requests[msg_id]["shell_msg"].get()
                with ycell.doc.transaction():
                    ycell["execution_count"] = msg["content"]["execution_count"]
                    ycell["execution_state"] = "idle"

    async def _handle_comms(self) -> None:
        if self.yjs is None or self.yjs.widgets is None:  # type: ignore
            return

        while True:
            msg = await self.comm_messages.get()
            msg_type = msg["header"]["msg_type"]
            if msg_type == "comm_open":
                comm_id = msg["content"]["comm_id"]
                comm = Comm(comm_id, self.shell_channel, self.session_id, self.key)
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
            await send_message(msg, self.shell_channel, self.key, change_date_to_str=True)
            msg = await receive_message(
                self.shell_channel, timeout=new_timeout, change_str_to_date=True
            )
            if msg is None:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            if msg["msg_type"] == "kernel_info_reply":
                msg = await receive_message(
                    self.iopub_channel, timeout=0.2, change_str_to_date=True
                )
                if msg is not None:
                    break
            new_timeout = deadline_to_timeout(deadline)

    async def _handle_outputs(self, outputs: Array, msg: Dict[str, Any]):
        msg_type = msg["header"]["msg_type"]
        content = msg["content"]
        if msg_type == "stream":
            with outputs.doc.transaction():
                # TODO: uncomment when changes are made in jupyter-ydoc
                if (not outputs) or (outputs[-1]["name"] != content["name"]):  # type: ignore
                    outputs.append(
                        #Map(
                        #    {
                        #        "name": content["name"],
                        #        "output_type": msg_type,
                        #        "text": Array([content["text"]]),
                        #    }
                        #)
                        {
                            "name": content["name"],
                            "output_type": msg_type,
                            "text": [content["text"]],
                        }
                    )
                else:
                    #outputs[-1]["text"].append(content["text"])  # type: ignore
                    last_output = outputs[-1]
                    last_output["text"].append(content["text"])  # type: ignore
                    outputs[-1] = last_output
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
                outputs.append(
                    {
                        "data": {"text/plain": [content["data"].get("text/plain", "")]},
                        "execution_count": content["execution_count"],
                        "metadata": {},
                        "output_type": msg_type,
                    }
                )
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
    def __init__(self, comm_id: str, shell_channel, session_id: str, key: str):
        self.comm_id = comm_id
        self.shell_channel = shell_channel
        self.session_id = session_id
        self.key = key
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
        asyncio.create_task(
            send_message(msg, self.shell_channel, self.key, change_date_to_str=True)
        )
