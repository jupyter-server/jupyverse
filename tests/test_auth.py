import pytest
from asphalt.core import Context
from jupyverse_api.auth import AuthConfig
from jupyverse_api.main import JupyverseComponent
from httpx import AsyncClient
from httpx_ws import WebSocketUpgradeError, aconnect_ws

from utils import authenticate_client, configure


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


@pytest.mark.asyncio
async def test_kernel_channels_unauthenticated(unused_tcp_port):
    async with Context() as ctx:
        await JupyverseComponent(
            components=COMPONENTS,
            port=unused_tcp_port,
        ).start(ctx)

        with pytest.raises(WebSocketUpgradeError):
            async with aconnect_ws(
                f"http://127.0.0.1:{unused_tcp_port}/api/kernels/kernel_id_0/channels?session_id=session_id_0",
            ):
                pass


@pytest.mark.asyncio
async def test_kernel_channels_authenticated(unused_tcp_port):
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=COMPONENTS,
            port=unused_tcp_port,
        ).start(ctx)

        await authenticate_client(http, unused_tcp_port)
        async with aconnect_ws(
            f"http://127.0.0.1:{unused_tcp_port}/api/kernels/kernel_id_0/channels?session_id=session_id_0",
            http,
        ):
            pass


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("noauth", "token", "user"))
async def test_root_auth(auth_mode, unused_tcp_port):
    components = configure(COMPONENTS, {"auth": {"mode": auth_mode}})
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/")
        if auth_mode == "noauth":
            expected = 302
        elif auth_mode in ["token", "user"]:
            expected = 403

        assert response.status_code == expected
        assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_no_auth(auth_mode, unused_tcp_port):
    components = configure(COMPONENTS, {"auth": {"mode": auth_mode}})
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/lab")
        assert response.status_code == 200


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("token",))
async def test_token_auth(auth_mode, unused_tcp_port):
    components = configure(COMPONENTS, {"auth": {"mode": auth_mode}})
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

        auth_config = await ctx.request_resource(AuthConfig)

        # no token provided, should not work
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/")
        assert response.status_code == 403
        # token provided, should work
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/?token={auth_config.token}")
        assert response.status_code == 302


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("user",))
@pytest.mark.parametrize(
    "permissions",
    (
        {},
        {"admin": ["read"], "foo": ["bar", "baz"]},
    ),
)
async def test_permissions(auth_mode, permissions, unused_tcp_port):
    components = configure(COMPONENTS, {"auth": {"mode": auth_mode}})
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

        await authenticate_client(http, unused_tcp_port, permissions=permissions)
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/auth/user/me")
        if "admin" in permissions.keys():
            # we have the permissions
            assert response.status_code == 200
        else:
            # we don't have the permissions
            assert response.status_code == 403
