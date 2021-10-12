from uuid import uuid4
import socket
import subprocess
import time
import asyncio

import pytest

pytest_plugins = ("fps.testing.fixtures",)


@pytest.fixture(scope="session")
def event_loop():
    """Change event_loop fixture to module level."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture()
def authenticated_user(client):
    username = uuid4().hex
    # who am I?
    response = client.get("/auth/users/me")
    if response.status_code != 401:
        response = client.post("/logout")
    # register user
    register_body = {
        "email": username + "@example.com",
        "password": username,
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
        "name": username,
        "username": username,
        "color": "",
    }
    response = client.post("/register", json=register_body)
    assert response.status_code == 201
    # login with registered user
    login_body = {"username": username + "@example.com", "password": username}
    assert "fastapiusersauth" not in client.cookies
    response = client.post("/login", data=login_body)
    assert "fastapiusersauth" in client.cookies
    # who am I?
    response = client.get("/auth/users/me")
    assert response.status_code != 401
    return username


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


@pytest.fixture()
def start_jupyverse(auth_mode, clear_users, capfd):
    port = get_open_port()
    command_list = [
        "jupyverse",
        "--no-open-browser",
        f"--authenticator.mode={auth_mode}",
        "--authenticator.clear_users=" + str(clear_users).lower(),
        f"--port={port}",
    ]
    p = subprocess.Popen(command_list)
    while True:
        time.sleep(0.5)
        out, err = capfd.readouterr()
        if "Application startup complete" in err:
            break
    url = f"http://127.0.0.1:{port}"
    yield url
    p.kill()
