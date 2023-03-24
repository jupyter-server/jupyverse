import asyncio
import json
import os
import signal
import uuid
from datetime import datetime
from typing import Dict, Iterable, List, Optional, cast

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..kernel_driver.connect import cfg_t, connect_channel
from ..kernel_driver.connect import launch_kernel as _launch_kernel
from ..kernel_driver.connect import read_connection_file
from ..kernel_driver.connect import (
    write_connection_file as _write_connection_file,
)
from ..kernel_driver.message import create_message, receive_message, send_message
from .message import (
    deserialize_msg_from_ws_v1,
    from_binary,
    get_msg_from_parts,
    get_parent_header,
    get_zmq_parts,
    send_raw_message,
    serialize_msg_to_ws_v1,
    to_binary,
)

kernels: dict = {}


class AcceptedWebSocket:
    _websocket: WebSocket
    _accepted_subprotocol: Optional[str]

    def __init__(self, websocket, accepted_subprotocol):
        self._websocket = websocket
        self._accepted_subprotocol = accepted_subprotocol

    @property
    def websocket(self):
        return self._websocket

    @property
    def accepted_subprotocol(self):
        return self._accepted_subprotocol


class KernelServer:
    def __init__(
        self,
        kernelspec_path: str = "",
        kernel_cwd: str = "",
        connection_cfg: Optional[cfg_t] = None,
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
    ) -> None:
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path
        self.kernel_cwd = kernel_cwd
        self.connection_cfg = connection_cfg
        self.connection_file = connection_file
        self.write_connection_file = write_connection_file
        self.channel_tasks: List[asyncio.Task] = []
        self.sessions: Dict[str, AcceptedWebSocket] = {}
        # blocked messages and allowed messages are mutually exclusive
        self.blocked_messages: List[str] = []
        self.allowed_messages: Optional[List[str]] = None  # when None, all messages are allowed
        # when [], no message is allowed
        self.setup_connection_file()

    def setup_connection_file(self):
        if self.write_connection_file:
            self.connection_file_path, self.connection_cfg = _write_connection_file(
                self.connection_file
            )
        elif self.connection_file:
            self.connection_file_path = self.connection_file
            self.connection_cfg = read_connection_file(self.connection_file)
        else:
            if self.connection_cfg is None:
                raise RuntimeError("No connection_cfg")
        self.key = cast(str, self.connection_cfg["key"])

    def block_messages(self, message_types: Iterable[str] = []):
        # if using blocked messages, discard allowed messages
        self.allowed_messages = None
        if isinstance(message_types, str):
            message_types = [message_types]
        self.blocked_messages = list(message_types)

    def allow_messages(self, message_types: Optional[Iterable[str]] = None):
        # if using allowed messages, discard blocked messages
        self.blocked_messages = []
        if message_types is None:
            self.allowed_messages = None
            return
        if isinstance(message_types, str):
            message_types = [message_types]
        self.allowed_messages = list(message_types)

    @property
    def connections(self) -> int:
        return len(self.sessions)

    async def start(self, launch_kernel: bool = True) -> None:
        self.last_activity = {
            "date": datetime.utcnow().isoformat() + "Z",
            "execution_state": "starting",
        }
        if launch_kernel:
            if not self.kernelspec_path:
                raise RuntimeError("Could not find a kernel, maybe you forgot to install one?")
            self.kernel_process = await _launch_kernel(
                self.kernelspec_path,
                self.connection_file_path,
                self.kernel_cwd,
                self.capture_kernel_output,
            )
        assert self.connection_cfg is not None
        identity = uuid.uuid4().hex.encode("ascii")
        self.shell_channel = connect_channel("shell", self.connection_cfg, identity=identity)
        self.stdin_channel = connect_channel("stdin", self.connection_cfg, identity=identity)
        self.control_channel = connect_channel("control", self.connection_cfg, identity=identity)
        self.iopub_channel = connect_channel("iopub", self.connection_cfg)
        await self._wait_for_ready()
        self.channel_tasks += [
            asyncio.create_task(self.listen("shell")),
            asyncio.create_task(self.listen("stdin")),
            asyncio.create_task(self.listen("control")),
            asyncio.create_task(self.listen("iopub")),
        ]

    async def stop(self) -> None:
        if self.write_connection_file:
            # FIXME: stop kernel in a better way
            try:
                self.kernel_process.send_signal(signal.SIGINT)
                self.kernel_process.kill()
                await self.kernel_process.wait()
            except BaseException:
                pass
            try:
                os.remove(self.connection_file_path)
            except BaseException:
                pass
        for task in self.channel_tasks:
            task.cancel()
        self.channel_tasks = []

    def interrupt(self) -> None:
        self.kernel_process.send_signal(signal.SIGINT)

    async def restart(self) -> None:
        await self.stop()
        self.setup_connection_file()
        await self.start()

    async def serve(
        self,
        websocket: AcceptedWebSocket,
        session_id: str,
        permissions: Optional[Dict[str, List[str]]],
    ):
        self.sessions[session_id] = websocket
        self.can_execute = permissions is None or "execute" in permissions.get("kernels", [])
        await self.listen_web(websocket)
        # the session could have been removed through the REST API, so check if it still exists
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def listen_web(self, websocket: AcceptedWebSocket):
        try:
            await self.send_to_zmq(websocket)
        except WebSocketDisconnect:
            pass

    async def listen(self, channel_name: str):
        if channel_name == "shell":
            channel = self.shell_channel
        elif channel_name == "control":
            channel = self.control_channel
        elif channel_name == "iopub":
            channel = self.iopub_channel
        elif channel_name == "stdin":
            channel = self.stdin_channel

        while True:
            parts = await get_zmq_parts(channel)
            parent_header = get_parent_header(parts)
            if channel == self.iopub_channel:
                # broadcast to all web clients
                for websocket in self.sessions.values():
                    await self.send_to_ws(websocket, parts, parent_header, channel_name)
            else:
                session = parent_header["session"]
                if session in self.sessions:
                    websocket = self.sessions[session]
                    await self.send_to_ws(websocket, parts, parent_header, channel_name)

    async def _wait_for_ready(self):
        while True:
            msg = create_message("kernel_info_request")
            await send_message(msg, self.shell_channel, self.key)
            msg = await receive_message(self.shell_channel, timeout=0.2)
            if msg is not None and msg["msg_type"] == "kernel_info_reply":
                msg = await receive_message(self.iopub_channel, timeout=0.2)
                if msg is None:
                    # IOPub not connected, start over
                    pass
                else:
                    break

    async def send_to_zmq(self, websocket):
        if not websocket.accepted_subprotocol:
            while True:
                msg = await receive_json_or_bytes(websocket.websocket)
                if not self.can_execute:
                    continue
                msg_type = msg["header"]["msg_type"]
                if (msg_type in self.blocked_messages) or (
                    self.allowed_messages is not None and msg_type not in self.allowed_messages
                ):
                    continue
                channel = msg.pop("channel")
                if channel == "shell":
                    await send_message(msg, self.shell_channel, self.key)
                elif channel == "control":
                    await send_message(msg, self.control_channel, self.key)
                elif channel == "stdin":
                    await send_message(msg, self.stdin_channel, self.key)
        elif websocket.accepted_subprotocol == "v1.kernel.websocket.jupyter.org":
            while True:
                msg = await websocket.websocket.receive_bytes()
                if not self.can_execute:
                    continue
                channel, parts = deserialize_msg_from_ws_v1(msg)
                # NOTE: we parse the header for message filtering
                # it is not as bad as parsing the content
                header = json.loads(parts[0])
                msg_type = header["msg_type"]
                if (msg_type in self.blocked_messages) or (
                    self.allowed_messages is not None and msg_type not in self.allowed_messages
                ):
                    continue
                if channel == "shell":
                    await send_raw_message(parts, self.shell_channel, self.key)
                elif channel == "control":
                    await send_raw_message(parts, self.control_channel, self.key)
                elif channel == "stdin":
                    await send_raw_message(parts, self.stdin_channel, self.key)

    async def send_to_ws(self, websocket, parts, parent_header, channel_name):
        if not websocket.accepted_subprotocol:
            # default, "legacy" protocol
            msg = get_msg_from_parts(parts, parent_header=parent_header)
            msg["channel"] = channel_name
            await send_json_or_bytes(websocket.websocket, msg)
            if channel_name == "iopub":
                if "content" in msg and "execution_state" in msg["content"]:
                    self.last_activity = {
                        "date": msg["header"]["date"],
                        "execution_state": msg["content"]["execution_state"],
                    }
        elif websocket.accepted_subprotocol == "v1.kernel.websocket.jupyter.org":
            bin_msg = serialize_msg_to_ws_v1(parts, channel_name)
            try:
                await websocket.websocket.send_bytes(bin_msg)
            except BaseException:
                pass
            # FIXME: update last_activity
            # but we don't want to parse the content!
            # or should we request it from the control channel?


async def receive_json_or_bytes(websocket):
    assert websocket.application_state == WebSocketState.CONNECTED
    message = await websocket.receive()
    websocket._raise_on_disconnect(message)
    if "text" in message:
        return json.loads(message["text"])
    msg = from_binary(message["bytes"])
    return msg


async def send_json_or_bytes(websocket, msg):
    bmsg = to_binary(msg)
    if bmsg is None:
        await websocket.send_json(msg)
    else:
        await websocket.send_bytes(bmsg)
