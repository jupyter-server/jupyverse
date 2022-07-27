import os
import socket
import subprocess
import time
from pathlib import Path
from uuid import uuid4

import pytest

pytest_plugins = (
    "fps.testing.fixtures",
    "fps_auth.fixtures",
)


@pytest.fixture()
def cwd():
    return Path(__file__).parent.parent


@pytest.fixture()
def authenticated_client(client):
    # create a new user
    username = uuid4().hex
    # if logged in, log out
    first_time = True
    while True:
        response = client.get("/auth/user/me")
        if response.status_code == 401:
            break
        assert first_time
        response = client.post("/auth/logout")
        first_time = False

    # register user
    register_body = {
        "email": username + "@example.com",
        "password": username,
        "username": username,
    }
    response = client.post("/auth/register", json=register_body)
    assert response.status_code == 201
    # check that we can't list users yet, since we're not logged in
    response = client.get("/auth/users")
    assert response.status_code == 401
    # log in with registered user
    login_body = {"username": username + "@example.com", "password": username}
    assert "fastapiusersauth" not in client.cookies
    response = client.post("/auth/login", data=login_body)
    assert response.status_code == 200
    # we should now have a cookie
    assert "fastapiusersauth" in client.cookies
    # check that we can list users now, since we are logged in
    response = client.get("/auth/users")
    assert response.status_code == 200
    users = response.json()
    assert username in [user["username"] for user in users]
    # who am I?
    response = client.get("/auth/user/me")
    assert response.status_code != 401
    me = response.json()
    assert me["username"] == username
    yield client


def get_open_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("", 0))
    s.listen(1)
    port = str(s.getsockname()[1])
    s.close()
    return port


@pytest.fixture()
def start_jupyverse(auth_mode, clear_users, cwd, capfd):
    os.chdir(cwd)
    port = get_open_port()
    command_list = [
        "jupyverse",
        "--no-open-browser",
        f"--authenticator.mode={auth_mode}",
        "--authenticator.clear_users=" + str(clear_users).lower(),
        f"--port={port}",
    ]
    print(" ".join(command_list))
    p = subprocess.Popen(command_list)
    dtime, ttime, timeout = 0.1, 0, 10
    while True:
        time.sleep(dtime)
        ttime += dtime
        if ttime >= timeout:
            raise RuntimeError("Timeout while launching Jupyverse")
        out, err = capfd.readouterr()
        if "Application startup complete" in err:
            break
    url = f"http://127.0.0.1:{port}"
    yield url
    p.kill()
