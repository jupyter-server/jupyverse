from typing import Optional
from uuid import uuid4

from anyio import Lock


async def authenticate_client(http, port, permissions={}):
    # create a new user
    username = uuid4().hex
    # if logged in, log out
    first_time = True
    while True:
        response = await http.get(f"http://127.0.0.1:{port}/api/me")
        if response.status_code == 403:
            break
        assert first_time
        response = await http.post(f"http://127.0.0.1:{port}/auth/logout")
        assert response.status_code == 200
        first_time = False

    # register user
    register_body = {
        "email": f"{username}@example.com",
        "password": username,
        "username": username,
        "permissions": permissions,
    }
    response = await http.post(f"http://127.0.0.1:{port}/auth/register", json=register_body)
    # check that we cannot register if not logged in
    assert response.status_code == 403
    # log in as admin
    login_body = {"username": "admin@jupyter.com", "password": "jupyverse"}
    response = await http.post(f"http://127.0.0.1:{port}/auth/login", data=login_body)
    assert response.status_code == 204
    # register user
    response = await http.post(f"http://127.0.0.1:{port}/auth/register", json=register_body)
    assert response.status_code == 201

    # log out
    response = await http.post(f"http://127.0.0.1:{port}/auth/logout")
    assert response.status_code == 204
    # check that we can't get our identity, since we're not logged in
    response = await http.get(f"http://127.0.0.1:{port}/api/me")
    assert response.status_code == 403

    # log in with registered user
    login_body = {"username": f"{username}@example.com", "password": username}
    response = await http.post(f"http://127.0.0.1:{port}/auth/login", data=login_body)
    assert response.status_code == 204
    # we should now have a cookie
    assert "fastapiusersauth" in http.cookies
    # check our identity, since we're logged in
    response = await http.get(
        f"http://127.0.0.1:{port}/api/me", params={"permissions": permissions}
    )
    assert response.status_code == 200
    me = response.json()
    assert me["identity"]["username"] == username
    # check our permissions
    assert me["permissions"] == permissions


def create_content(
    content: Optional[list],
    type: str,
    size: Optional[int],
    mimetype: Optional[str],
    name: str,
    path: str,
    format: Optional[str],
) -> dict:
    return {
        "content": content,
        "created": None,
        "format": format,
        "last_modified": None,
        "mimetype": mimetype,
        "name": name,
        "path": path,
        "size": size,
        "type": type,
        "writable": True,
    }


def clear_content_values(content: dict, keys: list[str] = []):
    for k in content:
        if k in keys:
            content[k] = None
        if k == "content" and isinstance(content[k], list):
            for c in content[k]:
                clear_content_values(c, keys)
    return content


def sort_content_by_name(content: dict):
    for k in content:
        if k == "content" and isinstance(content[k], list):
            # FIXME: this sorting algorithm is terrible!
            names = [c["name"] for c in content[k]]
            names.sort()
            new_content = []
            for name in names:
                for i, c in enumerate(content[k]):
                    if c["name"] == name:
                        break
                content[k].pop(i)
                new_content.append(c)
            content[k] = new_content
            for c in content[k]:
                sort_content_by_name(c)
    return content


class Websocket:
    def __init__(self, websocket, path: str):
        self._websocket = websocket
        self._path = path
        self._send_lock = Lock()

    @property
    def path(self) -> str:
        return self._path

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        try:
            message = await self.recv()
        except Exception:
            raise StopAsyncIteration()
        return message

    async def send(self, message: bytes):
        async with self._send_lock:
            await self._websocket.send_bytes(message)

    async def recv(self) -> bytes:
        b = await self._websocket.receive_bytes()
        return bytes(b)
