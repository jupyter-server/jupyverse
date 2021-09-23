import pytest
from fastapi.testclient import TestClient
from fps_auth.routes import get_user_token

pytest_plugins = (
    "fps.testing.fixtures",
    "fps_auth.fixtures",
)


def test_kernel_channels(client, authenticated_user):
    with client.websocket_connect(
        "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        cookies=client.cookies,
    ):
        pass


@pytest.mark.parametrize("auth_mode", ("noauth", "token", "user"))
def test_root_auth(auth_mode, client):
    response = client.get("/")
    expected = 404
    if auth_mode == "noauth":
        expected = 200
    assert response.status_code == expected


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_no_auth(auth_mode, client, app):
    with TestClient(app) as client:
        response = client.get("/lab/api/settings")
    assert response.status_code == 200


@pytest.mark.parametrize("auth_mode", ("token",))
def test_token_auth(auth_mode, client, app):
    with TestClient(app) as client:
        user_token = get_user_token()
        response = client.get(f"/?token={user_token}")
    assert user_token is not None
    assert response.status_code == 200
