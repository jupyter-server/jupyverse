import os
from asyncio import sleep
from pathlib import Path

import pytest
from asphalt.core import Context
from fps_yjs.ywebsocket import WebsocketProvider
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from pycrdt import Doc, Text

from jupyverse_api.main import JupyverseComponent
from jupyverse_api.yjs.models import CreateDocumentSession, MergeRoom


@pytest.mark.asyncio
async def test_fork_room(tmp_path, unused_tcp_port):
    os.chdir(tmp_path)
    path = Path("foo.txt")
    path.write_text("Hello")

    components = {
        "app": {"type": "app"},
        "auth": {"type": "auth", "test": True, "mode": "noauth"},
        "contents": {"type": "contents"},
        "frontend": {"type": "frontend"},
        "yjs": {"type": "yjs"},
    }
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)
        await sleep(1)

        create_document_session = CreateDocumentSession(format="text", type="file")
        response = await http.put(
            f"http://127.0.0.1:{unused_tcp_port}/api/collaboration/session/{path}",
            json=create_document_session.model_dump(),
        )
        r = response.json()
        file_id = r["fileId"]

        # connect to root room
        async with aconnect_ws(
            f"http://127.0.0.1:{unused_tcp_port}/api/collaboration/room/text:file:{file_id}"
        ) as root_ws:
            # create a root room client
            root_ydoc = Doc()
            root_ydoc["source"] = root_ytext = Text()
            async with WebsocketProvider(root_ydoc, Websocket(root_ws, file_id)):
                await sleep(0.1)
                assert str(root_ytext) == "Hello"
                # fork room
                root_roomid = f"text:file:{file_id}"
                response = await http.put(
                    f"http://127.0.0.1:{unused_tcp_port}/api/collaboration/fork_room/{root_roomid}"
                )
                r = response.json()
                fork_roomid = r["roomId"]
                # connect to forked room
                async with aconnect_ws(
                    f"http://127.0.0.1:{unused_tcp_port}/api/collaboration/room/{fork_roomid}"
                ) as fork_ws:
                    # create a forked room client
                    fork_ydoc = Doc()
                    fork_ydoc["source"] = fork_ytext = Text()
                    async with WebsocketProvider(fork_ydoc, Websocket(fork_ws, fork_roomid)):
                        await sleep(0.1)
                        assert str(fork_ytext) == "Hello"
                        # check that the forked room is synced with the root room
                        root_ytext += ", World!"
                        await sleep(0.1)
                        assert str(root_ytext) == "Hello, World!"
                        assert str(fork_ytext) == "Hello, World!"
                        # check that the root room is not synced with the forked room
                        fork_ytext += " Bye!"
                        await sleep(0.1)
                        assert str(root_ytext) == "Hello, World!"
                        assert str(fork_ytext) == "Hello, World! Bye!"
                        # merge forked room into root room
                        merge_room = MergeRoom(fork_roomid=fork_roomid, root_roomid=root_roomid)
                        response = await http.put(
                            f"http://127.0.0.1:{unused_tcp_port}/api/collaboration/merge_room",
                            json=merge_room.model_dump(),
                        )
                        # check that the root room is synced with the forked room
                        await sleep(0.1)
                        assert str(root_ytext) == "Hello, World! Bye!"
                        assert str(fork_ytext) == "Hello, World! Bye!"


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
        except BaseException:
            raise StopAsyncIteration()
        return message

    async def send(self, message: bytes):
        await self.websocket.send_bytes(message)

    async def recv(self) -> bytes:
        b = await self.websocket.receive_bytes()
        return bytes(b)
