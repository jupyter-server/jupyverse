from uuid import uuid4

import pytest

pytest_plugins = ("fps.testing.fixtures",)  # "fps_auth.fixtures")


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
