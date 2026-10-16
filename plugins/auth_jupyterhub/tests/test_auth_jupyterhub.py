import json

import pytest
from fps import get_root_module
from httpx2 import ASGITransport, AsyncClient
from jupyterhub.services.auth import HubOAuth  # type: ignore[import-untyped]

pytestmark = pytest.mark.anyio

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "config": {
            "start_server": False,
        },
        "modules": {
            "app": {
                "type": "app",
            },
            "auth": {
                "type": "auth_jupyterhub",
            },
        },
    }
}

ACCESS_SCOPE = "access:servers!server=alice/"

HUB_USERS = {
    "alice-token": {"name": "alice", "scopes": [ACCESS_SCOPE]},
    "bob-token": {"name": "bob", "scopes": []},
    "charlie-token": {"name": "charlie", "scopes": ["access:servers!server=charlie/"]},
}


@pytest.fixture
def anyio_backend():
    # SQLAlchemy's async engine only supports asyncio
    return "asyncio"


@pytest.fixture
def hub(monkeypatch):
    monkeypatch.setenv("JUPYTERHUB_CLIENT_ID", "jupyterhub-user-alice")
    monkeypatch.setenv("JUPYTERHUB_OAUTH_ACCESS_SCOPES", json.dumps([ACCESS_SCOPE]))
    monkeypatch.delenv("JUPYTERHUB_ACTIVITY_URL", raising=False)

    def token_for_code(self, code, *, sync=True):
        return f"{code}-token"

    async def user_for_token(self, token, use_cache=True, session_id="", *, sync=True):
        return HUB_USERS[token]

    monkeypatch.setattr(HubOAuth, "token_for_code", token_for_code)
    monkeypatch.setattr(HubOAuth, "user_for_token", user_for_token)


async def log_in(client, code):
    # an unauthenticated request is redirected to the Hub, with the OAuth state in a cookie
    response = await client.get("/api/me")
    assert response.status_code == 307
    ((cookie_name, state),) = response.cookies.items()
    client.cookies.set(cookie_name, state)
    # the Hub redirects back with a code, which is exchanged for a token
    response = await client.get("/oauth_callback", params={"code": code, "state": state})
    assert response.status_code == 307
    assert "jupyverse_jupyterhub_token" in client.cookies


async def test_api_me_permissions(hub):
    permissions = {"contents": ["read", "write"], "kernels": ["execute"]}
    async with get_root_module(CONFIG) as root_module:
        transport = ASGITransport(app=root_module.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await log_in(client, "alice")
            response = await client.get("/api/me", params={"permissions": json.dumps(permissions)})
            assert response.status_code == 200
            me = response.json()
            assert me["identity"]["username"] == "alice"
            assert me["permissions"] == permissions


@pytest.mark.parametrize("params", ({}, {"permissions": "null"}))
async def test_api_me_no_permissions(hub, params):
    async with get_root_module(CONFIG) as root_module:
        transport = ASGITransport(app=root_module.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await log_in(client, "alice")
            response = await client.get("/api/me", params=params)
            assert response.status_code == 200
            assert response.json()["permissions"] == {}


@pytest.mark.parametrize("code", ["bob", "charlie"], ids=["no-scopes", "other-server"])
async def test_api_me_requires_access_scope(hub, code):
    async with get_root_module(CONFIG) as root_module:
        transport = ASGITransport(app=root_module.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            await log_in(client, code)
            response = await client.get(
                "/api/me", params={"permissions": json.dumps({"contents": ["read"]})}
            )
            assert response.status_code == 403
