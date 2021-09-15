import pytest

pytest_plugins = ("fps_auth.fixtures",)


def test_kernel_channels(client, authenticated_user):
    with client.websocket_connect(
        "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        cookies=client.cookies,
    ):
        pass


@pytest.mark.parametrize("auth_mode", ("noauth", "token", "user"))
def test_root_auth(auth_mode, client):
    response = client.get("/")
    expected = 401
    if auth_mode == "noauth":
        expected = 200
    assert response.status_code == expected
