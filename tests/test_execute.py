import os
from functools import partial
from pathlib import Path

import pytest
from anyio import create_memory_object_stream, create_task_group, sleep
from asphalt.core import Context
from fps_yjs.ydocs import ydocs
from fps_yjs.ywebsocket import WebsocketProvider
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from pycrdt import Doc, Map, Text
from utils import configure

from jupyverse_api.main import JupyverseComponent

os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"

COMPONENTS = {
    "app": {"type": "app"},
    "auth": {"type": "auth", "test": True},
    "contents": {"type": "contents"},
    "frontend": {"type": "frontend"},
    "lab": {"type": "lab"},
    "jupyterlab": {"type": "jupyterlab"},
    "kernels": {"type": "kernels"},
    "yjs": {"type": "yjs"},
}


class Websocket:
    def __init__(self, websocket, roomid: str):
        self.websocket = websocket
        self.roomid = roomid

    @property
    def path(self) -> str:
        return self.roomid

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        try:
            message = await self.recv()
        except Exception:
            raise StopAsyncIteration()
        return message

    async def send(self, message: bytes):
        await self.websocket.send_bytes(message)

    async def recv(self) -> bytes:
        b = await self.websocket.receive_bytes()
        return bytes(b)


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_execute(auth_mode, unused_tcp_port):
    url = f"http://127.0.0.1:{unused_tcp_port}"
    components = configure(COMPONENTS, {
        "auth": {"mode": auth_mode},
        "kernels": {"require_yjs": True},
    })
    async with Context(), AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start()

        ws_url = url.replace("http", "ws", 1)
        name = "notebook1.ipynb"
        path = (Path("tests") / "data" / name).as_posix()
        # create a session to launch a kernel
        response = await http.post(
            f"{url}/api/sessions",
            json={
                "kernel": {"name": "python3"},
                "name": name,
                "path": path,
                "type": "notebook",
            },
        )
        r = response.json()
        kernel_id = r["kernel"]["id"]
        # get the room ID for the document
        response = await http.put(
            f"{url}/api/collaboration/session/{path}",
            json={
                "format": "json",
                "type": "notebook",
            },
            timeout=20,
        )
        file_id = response.json()["fileId"]
        document_id = f"json:notebook:{file_id}"
        ynb = ydocs["notebook"]()
        def callback(event_stream_send, events, event):
            events.append(event)
            event_stream_send.send_nowait(None)
        event_stream_send, event_stream_recv = create_memory_object_stream[None](1)
        events = []
        ynb.ydoc.observe_subdocs(partial(callback, event_stream_send, events))
        async with aconnect_ws(
            f"{ws_url}/api/collaboration/room/{document_id}"
        ) as websocket, WebsocketProvider(ynb.ydoc, Websocket(websocket, document_id)):
            # connect to the shared notebook document
            # wait for file to be loaded and Y model to be created in server and client
            await sleep(0.5)
            # execute notebook
            for cell_idx in range(2):
                response = await http.post(
                    f"{url}/api/kernels/{kernel_id}/execute",
                    json={
                        "document_id": document_id,
                        "cell_id": ynb.ycells[cell_idx]["id"],
                    }
                )
            while True:
                await event_stream_recv.receive()
                guid = None
                for event in events:
                    if event.added:
                        guid = event.added[0]
                if guid is not None:
                    break
            async with create_task_group() as tg:
                tg.start_soon(connect_ywidget, ws_url, guid)
                response = await http.post(
                    f"{url}/api/kernels/{kernel_id}/execute",
                    json={
                        "document_id": document_id,
                        "cell_id": ynb.ycells[2]["id"],
                    }
                )


async def connect_ywidget(ws_url, guid):
    ywidget_doc = Doc()
    async with aconnect_ws(
        f"{ws_url}/api/collaboration/room/ywidget:{guid}"
    ) as websocket, WebsocketProvider(ywidget_doc, Websocket(websocket, guid)):
        await sleep(0.5)
        ywidget_doc["_attrs"] = attrs = Map()
        ywidget_doc["_model_name"] = model_name = Text()
        assert str(model_name) == "Switch"
        assert str(attrs) == '{"value":true}'
