import os
import asyncio
import signal
from datetime import datetime
from typing import List, Dict, cast

from fastapi import WebSocket, WebSocketDisconnect  # type: ignore

from .connect import write_connection_file, launch_kernel, connect_channel
from .message import receive_message, send_message, create_message


class KernelServer:
    def __init__(
        self,
        kernelspec_path: str = "",
        connection_file: str = "",
        capture_kernel_output: bool = True,
    ) -> None:
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path
        if not self.kernelspec_path:
            raise RuntimeError(
                "Could not find a kernel, maybe you forgot to install one?"
            )
        self.connection_file_path, self.connection_cfg = write_connection_file(
            connection_file
        )
        self.key = cast(str, self.connection_cfg["key"])
        self.channel_tasks: List[asyncio.Task] = []
        self.sessions: Dict[str, WebSocket] = {}

    @property
    def connections(self) -> int:
        return len(self.sessions)

    async def start(self) -> None:
        self.last_activity = {
            "date": datetime.utcnow().isoformat() + "Z",
            "execution_state": "starting",
        }
        self.kernel_process = await launch_kernel(
            self.kernelspec_path, self.connection_file_path, self.capture_kernel_output
        )
        self.shell_channel = connect_channel("shell", self.connection_cfg)
        self.control_channel = connect_channel("control", self.connection_cfg)
        self.iopub_channel = connect_channel("iopub", self.connection_cfg)
        await self._wait_for_ready()
        self.channel_tasks += [
            asyncio.create_task(self.listen_shell()),
            asyncio.create_task(self.listen_control()),
            asyncio.create_task(self.listen_iopub()),
        ]

    async def stop(self) -> None:
        self.kernel_process.send_signal(signal.SIGINT)
        self.kernel_process.kill()
        await self.kernel_process.wait()
        os.remove(self.connection_file_path)
        for task in self.channel_tasks:
            task.cancel()
        self.channel_tasks = []

    async def restart(self) -> None:
        self.last_activity = {
            "date": datetime.utcnow().isoformat() + "Z",
            "execution_state": "starting",
        }
        for task in self.channel_tasks:
            task.cancel()
        self.channel_tasks = []
        msg = create_message("shutdown_request", content={"restart": True})
        send_message(msg, self.control_channel, self.key)
        while True:
            msg2 = await receive_message(self.control_channel)
            assert msg2 is not None
            if msg2["msg_type"] == "shutdown_reply" and msg2["content"]["restart"]:
                break
        await self._wait_for_ready()
        self.channel_tasks += [
            asyncio.create_task(self.listen_shell()),
            asyncio.create_task(self.listen_control()),
            asyncio.create_task(self.listen_iopub()),
        ]

    async def serve(self, websocket: WebSocket, session_id: str):
        self.sessions[session_id] = websocket
        await self.listen_web(websocket)
        del self.sessions[session_id]

    async def listen_web(self, websocket: WebSocket):
        try:
            while True:
                msg = await websocket.receive_json()
                channel = msg["channel"]
                msg = {
                    "header": msg["header"],
                    "msg_id": msg["header"]["msg_id"],
                    "msg_type": msg["header"]["msg_type"],
                    "parent_header": msg["parent_header"],
                    "content": msg["content"],
                    "metadata": msg["metadata"],
                }
                if channel == "shell":
                    send_message(msg, self.shell_channel, self.key)
                elif channel == "control":
                    send_message(msg, self.control_channel, self.key)
        except WebSocketDisconnect:
            pass

    async def listen_shell(self):
        while True:
            msg = await receive_message(self.shell_channel)
            msg["channel"] = "shell"
            session = msg["parent_header"]["session"]
            if session in self.sessions:
                websocket = self.sessions[session]
                await websocket.send_json(msg)

    async def listen_control(self):
        while True:
            msg = await receive_message(self.control_channel)
            msg["channel"] = "control"
            session = msg["parent_header"]["session"]
            if session in self.sessions:
                websocket = self.sessions[session]
                await websocket.send_json(msg)

    async def listen_iopub(self):
        while True:
            msg = await receive_message(self.iopub_channel)
            msg["channel"] = "iopub"
            for websocket in self.sessions.values():
                try:
                    await websocket.send_json(msg)
                except Exception:
                    pass
            if "content" in msg and "execution_state" in msg["content"]:
                self.last_activity = {
                    "date": msg["header"]["date"],
                    "execution_state": msg["content"]["execution_state"],
                }

    async def _wait_for_ready(self):
        while True:
            msg = create_message("kernel_info_request")
            send_message(msg, self.shell_channel, self.key)
            msg = await receive_message(self.shell_channel, 0.2)
            if msg is not None and msg["msg_type"] == "kernel_info_reply":
                msg = await receive_message(self.iopub_channel, 0.2)
                if msg is None:
                    # IOPub not connected, start over
                    pass
                else:
                    break
