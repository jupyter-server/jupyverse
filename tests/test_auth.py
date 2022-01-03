import pytest
from fastapi.testclient import TestClient
from fps_auth.config import get_auth_config

pytest_plugins = (
    "fps.testing.fixtures",
    "fps_auth.fixtures",
)


def test_kernel_channels_unauthenticated(client):
    with pytest.raises(KeyError):
        with client.websocket_connect(
            "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        ):
            pass


def test_kernel_channels_authenticated(client, authenticated_user):
    with client.websocket_connect(
        "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        cookies=client.cookies,
    ):
        pass


@pytest.mark.parametrize("auth_mode", ("noauth", "token", "user"))
def test_root_auth(auth_mode, client, app):
    with TestClient(app) as client:
        response = client.get("/")
        expected = 200
        content_type = "text/html; charset=utf-8"
        if auth_mode in ["token", "user"]:
            expected = 401
            content_type = "application/json"

    assert response.status_code == expected
    assert response.headers["content-type"] == content_type


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_no_auth(client, app):
    with TestClient(app) as client:
        response = client.get("/lab/api/settings")
    assert response.status_code == 200


@pytest.mark.parametrize("auth_mode", ("token",))
def test_token_auth(client, app):
    auth_config = get_auth_config()
    with TestClient(app) as client:
        response = client.get(f"/?token={auth_config.token}")
    assert response.status_code == 200
