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
def test_root_auth(auth_mode, client):
    response = client.get("/")
    expected = 200
    assert response.status_code == expected
    assert response.headers["content-type"] == "text/html; charset=utf-8"


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_no_auth(auth_mode, client, app):
    with TestClient(app) as client:
        response = client.get("/lab/api/settings")
    assert response.status_code == 200


@pytest.mark.parametrize("auth_mode", ("token",))
def test_token_auth(auth_mode, client, app):
    with TestClient(app) as client:
        auth_config = get_auth_config()
        response = client.get(f"/?token={auth_config.token}")
    assert auth_config.token is not None
    assert response.status_code == 200
