import pytest
from anyio import create_task_group
from fps import get_root_module
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from structlog.testing import capture_logs

from jupyverse_api.asgi_websocket_transport import ASGIWebSocketTransport
from jupyverse_api.yjs.models import CreateDocumentSession


@pytest.mark.anyio
async def test_concurrent_disconnect(tmp_path):
    config = {
        "jupyverse": {
            "type": "jupyverse",
                "config": {
                    "start_server": False,
                },
            "modules": {
                "app": {
                    "type": "app",
                },
                "yjs": {
                    "type": "yjs",
                    "config": {
                        "document_cleanup_delay": 0,
                    },
                },
                "auth": {
                    "type": "noauth",
                },
                "contents": {
                    "type": "contents",
                },
                "file_id": {
                    "type": "file_id",
                },
                "frontend": {
                    "type": "frontend",
                },
            },
        }
    }

    with capture_logs() as cap_logs:
        async with get_root_module(config) as root_module:
            app = root_module.app
            transport = ASGIWebSocketTransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://testserver") as client:
                data = CreateDocumentSession(format="text", type="file")
                p = tmp_path / "hello.txt"
                p.write_text("hello")
                response = await client.put(
                    f"http://testserver/api/collaboration/session/{p}",
                    json=dict(data),
                )
                data = response.json()
                file_id = data["fileId"]

                async def connect_ws():
                    async with aconnect_ws(
                        f"http://testserver/api/collaboration/room/text:file:{file_id}",
                        client,
                    ):
                        pass

                async with create_task_group() as tg:
                    tg.start_soon(connect_ws)
                    tg.start_soon(connect_ws)

    assert {
        "event": "Application failed",
        "log_level": "critical",
    } not in cap_logs
