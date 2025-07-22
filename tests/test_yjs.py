import asyncio
from collections.abc import AsyncGenerator
from unittest.mock import AsyncMock, MagicMock, patch

import anyio
import pytest
from fps import get_root_module, merge_config
from httpx_ws import aconnect_ws

from jupyverse_api.contents import Contents
from jupyverse_api.file_id import FileId
from jupyverse_api.yjs import Yjs

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "modules": {
            "app": {
                "type": "app",
            },
            "auth": {
                "type": "auth",
            },
            "contents": {
                "type": "contents",
            },
            "file_id": {
                "type": "file_id",
            },
            "yjs": {
                "type": "yjs",
                "config": {
                    "document_cleanup_delay": 0,
                }
            },
        },
    }
}

@pytest.fixture
async def patched(unused_tcp_port) -> AsyncGenerator[tuple[Yjs, int], None]:
    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": unused_tcp_port}}})
    async with get_root_module(config) as jupyverse_module:
        # patch aiosqlite
        with patch("fps_yjs.ywebsocket.ystore.connect"):
            yjs = await jupyverse_module.get(Yjs)
            fileid = await jupyverse_module.get(FileId)
            contents = await jupyverse_module.get(Contents)
            yjs.get_file_path = MagicMock(return_value="test.ipynb")
            fileid.get_path = AsyncMock(return_value="test.ipynb")
            mock_content = MagicMock(last_modified="2021-01-01T00:00:00Z")
            contents.read_content = AsyncMock(return_value=mock_content)
            contents.write_content = AsyncMock()
            yield yjs, unused_tcp_port

@pytest.mark.anyio
async def test_room_cleanup(patched: tuple[Yjs, int]):
        yjs, unused_tcp_port = patched
        collaboration_url = f"http://127.0.0.1:{unused_tcp_port}/api/collaboration/room/json:notebook:1234567890"
        async with aconnect_ws(
                collaboration_url,
            ) as first_ws:
            async with aconnect_ws(
                collaboration_url,
            ) as second_ws:
                await asyncio.gather(
                    # sleep to make sure these two websockets are closed at the exact same time
                    anyio.sleep(0.1),
                    first_ws.close(),
                    second_ws.close(),
                )

        # wait for the room to be cleaned up
        await anyio.sleep(0.1)
        assert not yjs.room_manager.websocket_server.rooms
