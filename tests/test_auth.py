import pytest
from fps_auth.config import get_auth_config
from starlette.websockets import WebSocketDisconnect


def test_kernel_channels_unauthenticated(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        ):
            pass


def test_kernel_channels_authenticated(authenticated_client):
    with authenticated_client.websocket_connect(
        "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
    ):
        pass


@pytest.mark.parametrize("auth_mode", ("noauth", "token", "user"))
def test_root_auth(auth_mode, client):
    response = client.get("/")
    if auth_mode == "noauth":
        expected = 200
        content_type = "text/html; charset=utf-8"
    elif auth_mode in ["token", "user"]:
        expected = 403
        content_type = "application/json"

    assert response.status_code == expected
    assert response.headers["content-type"] == content_type


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_no_auth(client):
    response = client.get("/lab/api/settings")
    assert response.status_code == 200


@pytest.mark.parametrize("auth_mode", ("token",))
def test_token_auth(client):
    # no token provided, should not work
    response = client.get("/")
    assert response.status_code == 403
    # token provided, should work
    auth_config = get_auth_config()
    response = client.get(f"/?token={auth_config.token}")
    assert response.status_code == 200


@pytest.mark.parametrize("auth_mode", ("user",))
@pytest.mark.parametrize(
    "permissions",
    (
        {},
        {"admin": ["read"], "foo": ["bar", "baz"]},
    ),
)
def test_permissions(authenticated_client, permissions):
    response = authenticated_client.get("/auth/user/me")
    if "admin" in permissions.keys():
        # we have the permissions
        assert response.status_code == 200
    else:
        # we don't have the permissions
        assert response.status_code == 403
