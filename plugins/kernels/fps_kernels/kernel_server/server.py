from __future__ import annotations

import json
from collections.abc import Iterable
from datetime import datetime, timezone

from anyio import TASK_STATUS_IGNORED, Event, create_task_group, move_on_after
from anyio.abc import TaskStatus
from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from jupyverse_api.kernel import DefaultKernelFactory, KernelFactory

from ..kernel_driver.message import (
    DELIM,
    create_message,
    deserialize_message,
    feed_identities,
    serialize_message,
    sign,
)
from .message import (
    deserialize_msg_from_ws_v1,
    from_binary,
    get_parent_header,
    serialize_msg_to_ws_v1,
    to_binary,
)

kernels: dict = {}


class AcceptedWebSocket:
    _websocket: WebSocket
    _accepted_subprotocol: str | None

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
        default_kernel_factory: DefaultKernelFactory,
        kernelspec_path: str = "",
        kernel_cwd: str = "",
        connection_file: str = "",
        write_connection_file: bool = True,
        capture_kernel_output: bool = True,
    ) -> None:
        self.default_kernel_factory = default_kernel_factory
        self.capture_kernel_output = capture_kernel_output
        self.kernelspec_path = kernelspec_path
        self.kernel_cwd = kernel_cwd
        self.connection_file = connection_file
        self.write_connection_file = write_connection_file
        self.sessions: dict[str, AcceptedWebSocket] = {}
        # blocked messages and allowed messages are mutually exclusive
        self.blocked_messages: list[str] = []
        self.allowed_messages: list[str] | None = None  # when None, all messages are allowed
        # when [], no message is allowed

    def block_messages(self, message_types: Iterable[str] = []):
        # if using blocked messages, discard allowed messages
        self.allowed_messages = None
        if isinstance(message_types, str):
            message_types = [message_types]
        self.blocked_messages = list(message_types)

    def allow_messages(self, message_types: Iterable[str] | str | None = None):
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

    async def start(
        self,
        launch_kernel: bool = True,
        kernel_factory: KernelFactory | None = None,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
    ) -> None:
        async with create_task_group() as self.task_group:
            self.last_activity = {
                "date": datetime.now(tz=timezone.utc).isoformat().replace("+00:00", "Z"),
                "execution_state": "starting",
            }
            if launch_kernel:
                if not self.kernelspec_path:
                    raise RuntimeError("Could not find a kernel, maybe you forgot to install one?")
                if kernel_factory is None:
                    self.kernel = self.default_kernel_factory(
                        write_connection_file=self.write_connection_file,
                        kernelspec_path=self.kernelspec_path,
                        connection_file=self.connection_file,
                        kernel_cwd=self.kernel_cwd,
                        capture_output=self.capture_kernel_output,
                    )
                else:
                    self.kernel = kernel_factory(
                        kernelspec_path=self.kernelspec_path,
                        connection_file=self.connection_file,
                        kernel_cwd=self.kernel_cwd,
                        capture_output=self.capture_kernel_output,
                    )
                await self.task_group.start(self.kernel.start)
            task_status.started()
            if self.kernel.wait_for_ready:
                await self._wait_for_ready()
            async with create_task_group() as tg:
                tg.start_soon(lambda: self.listen("shell"))
                tg.start_soon(lambda: self.listen("stdin"))
                tg.start_soon(lambda: self.listen("control"))
                tg.start_soon(lambda: self.listen("iopub"))

    async def stop(self) -> None:
        await self.kernel.stop()
        self.task_group.cancel_scope.cancel()

    async def interrupt(self) -> None:
        await self.kernel.interrupt()

    async def restart(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        await self.stop()
        await self.start(task_status=task_status)

    async def serve(
        self,
        websocket: AcceptedWebSocket,
        session_id: str,
        permissions: dict[str, list[str]] | None,
    ):
        self.sessions[session_id] = websocket
        self.can_execute = permissions is None or "execute" in permissions.get("kernels", [])
        stop_event = Event()
        self.task_group.start_soon(self.listen_web, websocket, stop_event)
        await stop_event.wait()

        # the session could have been removed through the REST API, so check if it still exists
        if session_id in self.sessions:
            del self.sessions[session_id]

    async def listen_web(self, websocket: AcceptedWebSocket, stop_event: Event):
        try:
            await self.send_to_kernel(websocket)
        except WebSocketDisconnect:
            pass
        finally:
            stop_event.set()

    async def listen(self, channel_name: str):
        channel = {
            "shell": self.kernel.shell_stream,
            "control": self.kernel.control_stream,
            "iopub": self.kernel.iopub_stream,
            "stdin": self.kernel.stdin_stream,
        }[channel_name]

        while True:
            msg = await channel.receive()
            idents, parts = feed_identities(msg)
            parent_header = get_parent_header(parts)
            if channel_name == "iopub":
                # broadcast to all web clients
                websockets = list(self.sessions.values())
                for websocket in websockets:
                    await self.send_to_ws(websocket, parts, parent_header, channel_name)
            else:
                session = parent_header["session"]
                if session in self.sessions:
                    websocket = self.sessions[session]
                    await self.send_to_ws(websocket, parts, parent_header, channel_name)

    async def _wait_for_ready(self) -> None:
        while True:
            msg = create_message("kernel_info_request")
            msg_ser = serialize_message(msg, self.kernel.key)
            await self.kernel.shell_stream.send(msg_ser)
            with move_on_after(0.2) as scope:
                msg_ser = await self.kernel.shell_stream.receive()
                idents, msg_list = feed_identities(msg_ser)
                msg = deserialize_message(msg_list)
            if not scope.cancelled_caught and msg["msg_type"] == "kernel_info_reply":
                with move_on_after(0.2) as scope:
                    msg_ser = await self.kernel.iopub_stream.receive()
                    idents, msg_list = feed_identities(msg_ser)
                    msg = deserialize_message(msg_list)
                if scope.cancelled_caught:
                    # IOPub not connected, start over
                    pass
                else:
                    return

    async def send_to_kernel(self, websocket):
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
                msg_ser = serialize_message(msg, self.kernel.key)
                if channel == "shell":
                    await self.kernel.shell_stream.send(msg_ser)
                elif channel == "control":
                    await self.kernel.control_stream.send(msg_ser)
                elif channel == "stdin":
                    await self.kernel.stdin_stream.send(msg_ser)
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
                msg = parts[:4]
                buffers = parts[4:]
                to_send = [DELIM, sign(msg, self.kernel.key)] + msg + buffers
                if channel == "shell":
                    await self.kernel.shell_stream.send(to_send)
                elif channel == "control":
                    await self.kernel.control_stream.send(to_send)
                elif channel == "stdin":
                    await self.kernel.stdin_stream.send(to_send)

    async def send_to_ws(self, websocket, parts, parent_header, channel_name):
        if not websocket.accepted_subprotocol:
            # default, "legacy" protocol
            msg = deserialize_message(parts, parent_header=parent_header)
            msg["channel"] = channel_name
            await send_json_or_bytes(websocket.websocket, msg)
            if channel_name == "iopub":
                if "content" in msg and "execution_state" in msg["content"]:
                    self.last_activity = {
                        "date": msg["header"]["date"],
                        "execution_state": msg["content"]["execution_state"],
                    }
        elif websocket.accepted_subprotocol == "v1.kernel.websocket.jupyter.org":
            bin_msg = b"".join(serialize_msg_to_ws_v1(parts, channel_name))
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
