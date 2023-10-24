import pytest
from asphalt.core import Context
from fastapi import APIRouter
from httpx import AsyncClient
from utils import configure

from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.main import JupyverseComponent


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mount_path",
    (
        None,
        "/foo",
    ),
)
async def test_mount_path(mount_path, unused_tcp_port):
    components = configure({"app": {"type": "app"}}, {"app": {"mount_path": mount_path}})

    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

        app = await ctx.request_resource(App)
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
