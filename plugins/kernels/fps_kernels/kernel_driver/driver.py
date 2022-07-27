import asyncio
import os
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple, cast

from zmq.asyncio import Socket

from .connect import cfg_t, connect_channel, launch_kernel, read_connection_file
from .connect import write_connection_file as _write_connection_file
from .kernelspec import find_kernelspec
from .message import create_message, deserialize, serialize

DELIM = b"<IDS|MSG>"


def deadline_to_timeout(deadline: float) -> float:
    return max(0, deadline - time.time())


def feed_identities(msg_list: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
    idx = msg_list.index(DELIM)
    return msg_list[:idx], msg_list[idx + 1 :]  # noqa


def send_message(msg: Dict[str, Any], sock: Socket, key: str) -> None:
    to_send = serialize(msg, key)
    sock.send_multipart(to_send, copy=True)


async def receive_message(sock: Socket, timeout: float = float("inf")) -> Optional[Dict[str, Any]]:
    timeout *= 1000  # in ms
    ready = await sock.poll(timeout)
    if ready:
        msg_list = await sock.recv_multipart()
        idents, msg_list = feed_identities(msg_list)
        return deserialize(msg_list)
    return None


class KernelDriver:
    def __init__(
        self,
        kernel_name: str = "",
        kernelspec_path: str = "",
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
    ) -> None:
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path or find_kernelspec(kernel_name)
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
        self.execute_requests: Dict[str, Dict[str, asyncio.Future]] = {}
        self.channel_tasks: List[asyncio.Task] = []

    async def restart(self, startup_timeout: float = float("inf")) -> None:
        for task in self.channel_tasks:
            task.cancel()
        msg = create_message("shutdown_request", content={"restart": True})
        send_message(msg, self.control_channel, self.key)
        while True:
            msg = cast(Dict[str, Any], await receive_message(self.control_channel))
            if msg["msg_type"] == "shutdown_reply" and msg["content"]["restart"]:
                break
        await self._wait_for_ready(startup_timeout)
        self.channel_tasks = []
        self.listen_channels()

    async def start(self, startup_timeout: float = float("inf"), connect: bool = True) -> None:
        self.kernel_process = await launch_kernel(
            self.kernelspec_path, self.connection_file_path, self.capture_kernel_output
        )
        if connect:
            await self.connect(startup_timeout)

    async def connect(self, startup_timeout: float = float("inf")) -> None:
        self.connect_channels()
        await self._wait_for_ready(startup_timeout)
        self.listen_channels()

    def connect_channels(self, connection_cfg: cfg_t = None):
        connection_cfg = connection_cfg or self.connection_cfg
        self.shell_channel = connect_channel("shell", connection_cfg)
        self.control_channel = connect_channel("control", connection_cfg)
        self.iopub_channel = connect_channel("iopub", connection_cfg)

    def listen_channels(self):
        self.channel_tasks.append(asyncio.create_task(self.listen_iopub()))
        self.channel_tasks.append(asyncio.create_task(self.listen_shell()))

    async def stop(self) -> None:
        self.kernel_process.kill()
        await self.kernel_process.wait()
        os.remove(self.connection_file_path)
        for task in self.channel_tasks:
            task.cancel()

    async def listen_iopub(self):
        while True:
            msg = await receive_message(self.iopub_channel)  # type: ignore
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests.keys():
                self.execute_requests[msg_id]["iopub_msg"].set_result(msg)

    async def listen_shell(self):
        while True:
            msg = await receive_message(self.shell_channel)  # type: ignore
            msg_id = msg["parent_header"].get("msg_id")
            if msg_id in self.execute_requests.keys():
                self.execute_requests[msg_id]["shell_msg"].set_result(msg)

    async def execute(
        self,
        cell: Dict[str, Any],
        timeout: float = float("inf"),
        msg_id: str = "",
        wait_for_executed: bool = True,
    ) -> None:
        if cell["cell_type"] != "code":
            return
        content = {"code": cell["source"], "silent": False}
        msg = create_message(
            "execute_request", content, session_id=self.session_id, msg_cnt=self.msg_cnt
        )
        if msg_id:
            msg["header"]["msg_id"] = msg_id
        else:
            msg_id = msg["header"]["msg_id"]
        self.msg_cnt += 1
        send_message(msg, self.shell_channel, self.key)
        if wait_for_executed:
            deadline = time.time() + timeout
            self.execute_requests[msg_id] = {
                "iopub_msg": asyncio.Future(),
                "shell_msg": asyncio.Future(),
            }
            while True:
                try:
                    await asyncio.wait_for(
                        self.execute_requests[msg_id]["iopub_msg"],
                        deadline_to_timeout(deadline),
                    )
                except asyncio.TimeoutError:
                    error_message = f"Kernel didn't respond in {timeout} seconds"
                    raise RuntimeError(error_message)
                msg = self.execute_requests[msg_id]["iopub_msg"].result()
                self._handle_outputs(cell["outputs"], msg)
                if (
                    msg["header"]["msg_type"] == "status"
                    and msg["content"]["execution_state"] == "idle"
                ):
                    break
                self.execute_requests[msg_id]["iopub_msg"] = asyncio.Future()
            try:
                await asyncio.wait_for(
                    self.execute_requests[msg_id]["shell_msg"],
                    deadline_to_timeout(deadline),
                )
            except asyncio.TimeoutError:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            msg = self.execute_requests[msg_id]["shell_msg"].result()
            cell["execution_count"] = msg["content"]["execution_count"]
            del self.execute_requests[msg_id]

    async def _wait_for_ready(self, timeout):
        deadline = time.time() + timeout
        new_timeout = timeout
        while True:
            msg = create_message(
                "kernel_info_request", session_id=self.session_id, msg_cnt=self.msg_cnt
            )
            self.msg_cnt += 1
            send_message(msg, self.shell_channel, self.key)
            msg = await receive_message(self.shell_channel, new_timeout)
            if msg is None:
                error_message = f"Kernel didn't respond in {timeout} seconds"
                raise RuntimeError(error_message)
            if msg["msg_type"] == "kernel_info_reply":
                msg = await receive_message(self.iopub_channel, 0.2)
                if msg is not None:
                    break
            new_timeout = deadline_to_timeout(deadline)

    def _handle_outputs(self, outputs: List[Dict[str, Any]], msg: Dict[str, Any]):
        msg_type = msg["header"]["msg_type"]
        content = msg["content"]
        if msg_type == "stream":
            if (not outputs) or (outputs[-1]["name"] != content["name"]):
                outputs.append({"name": content["name"], "output_type": msg_type, "text": []})
            outputs[-1]["text"].append(content["text"])
        elif msg_type in ("display_data", "execute_result"):
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
        else:
            return
