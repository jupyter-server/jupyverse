from socket import socket

import pytest


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture()
def unused_tcp_port() -> int:
    with socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
