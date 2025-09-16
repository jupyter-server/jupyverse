import pytest
from fastapi import APIRouter
from fps import get_root_module
from httpx import AsyncClient
from jupyverse_api.app import App

from jupyverse_api import Router


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
            "config": {
                "port": unused_tcp_port,
            },
            "modules": {
                "app": {"type": "app", "config": {"mount_path": mount_path}},
            },
        }
    }

    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with AsyncClient() as http, root_module as jupyverse_module:
        app = await jupyverse_module.get(App)
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
