import pytest

from fastaio import get_root_component
from fastapi import APIRouter
from httpx import AsyncClient
from utils import configure

from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.main import JupyverseComponent


@pytest.mark.anyio
@pytest.mark.parametrize(
    "mount_path",
    (
        None,
        "/foo",
    ),
)
async def test_mount_path(mount_path, unused_tcp_port):
    config = {
        "jupyverse": {
            "type": "jupyverse",
            "components": {
                "app": {
                    "type": "app",
                    "config": {
                        "mout_path": mount_path
                    }
                },
            }
        }
    }

    async with AsyncClient() as http, get_root_component(config) as jupyverse_component:
        app = await jupyverse_component.get_resource(App)
        router = APIRouter()

        @router.get("/")
        async def get():
            pass

        Router(app).include_router(router)

        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}")
        expected = 200 if mount_path is None else 404
        assert response.status_code == expected

        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/bar")
        assert response.status_code == 404

        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/foo")
        expected = 404 if mount_path is None else 200
