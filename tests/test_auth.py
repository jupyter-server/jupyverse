def test_kernel_channels(client):
    # who am I? unauthorized
    response = client.get("/auth/users/me")
    assert response.status_code == 401
    # register user
    register_body = {
        "email": "user@example.com",
        "password": "string",
        "is_active": True,
        "is_superuser": False,
        "is_verified": False,
        "name": "string",
        "username": "string",
        "color": "string",
    }
    response = client.post("/register", json=register_body)
    assert (
        response.status_code == 201 or response.status_code == 400
    )  # 400: already exists
    # login with registered user
    login_body = {"username": "user@example.com", "password": "string"}
    assert "fastapiusersauth" not in client.cookies
    response = client.post("/login", data=login_body)
    assert "fastapiusersauth" in client.cookies
    # who am I?
    response = client.get("/auth/users/me")
    assert response.status_code != 401
    with client.websocket_connect(
        "/api/kernels/kernel_id_0/channels?session_id=session_id_0",
        cookies=client.cookies,
    ):
        pass
