from uuid import uuid4

import pytest  # type: ignore
from fps_auth.config import AuthConfig, get_auth_config


@pytest.fixture
def auth_mode():
    return "token"


@pytest.fixture
def auth_config(auth_mode):
    yield AuthConfig.parse_obj({"mode": auth_mode, "test": True})


@pytest.fixture
def config_override(app, auth_config):
    async def override_get_config():
        return auth_config

    app.dependency_overrides[get_auth_config] = override_get_config


@pytest.fixture()
def permissions():
    return {}


@pytest.fixture()
def authenticated_client(client, permissions):
    # create a new user
    username = uuid4().hex
    # if logged in, log out
    first_time = True
    while True:
        response = client.get("/api/me")
        if response.status_code == 403:
            break
        assert first_time
        response = client.post("/auth/logout")
        assert response.status_code == 200
        first_time = False

    # register user
    register_body = {
        "email": username + "@example.com",
        "password": username,
        "username": username,
        "permissions": permissions,
    }
    response = client.post("/auth/register", json=register_body)
    # check that we cannot register if not logged in
    assert response.status_code == 403
    # log in as admin
    login_body = {"username": "admin@jupyter.com", "password": "jupyverse"}
    response = client.post("/auth/login", data=login_body)
    assert response.status_code == 200
    # register user
    response = client.post("/auth/register", json=register_body)
    assert response.status_code == 201

    # log out
    response = client.post("/auth/logout")
    assert response.status_code == 200
    # check that we can't get our identity, since we're not logged in
    response = client.get("/api/me")
    assert response.status_code == 403

    # log in with registered user
    login_body = {"username": username + "@example.com", "password": username}
    response = client.post("/auth/login", data=login_body)
    assert response.status_code == 200
    # we should now have a cookie
    assert "fastapiusersauth" in client.cookies
    # check our identity, since we're logged in
    response = client.get("/api/me", json={"permissions": permissions})
    assert response.status_code == 200
    me = response.json()
    assert me["identity"]["username"] == username
    # check our permissions
    assert me["permissions"] == permissions
    yield client
