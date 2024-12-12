import os
import signal
import subprocess
import time
from pathlib import Path

import pytest
import requests


@pytest.fixture
def anyio_backend():
    # at least, SQLAlchemy doesn't support anything else than asyncio
    return "asyncio"


@pytest.fixture()
def cwd():
    return Path(__file__).parents[1]


@pytest.fixture()
def start_jupyverse(auth_mode, clear_users, cwd, unused_tcp_port):
    os.chdir(cwd)
    command_list = [
        "jupyverse",
        "--set",
        f"auth.mode={auth_mode}",
        "--set",
        f"auth.clear_users={str(clear_users).lower()}",
        "--set",
        "kernels.require_yjs=true",
        "--port",
        str(unused_tcp_port),
    ]
    p = subprocess.Popen(command_list)
    url = f"http://127.0.0.1:{unused_tcp_port}"
    while True:
        try:
            requests.get(url)
        except requests.exceptions.ConnectionError:
            time.sleep(0.1)
        else:
            break
    yield url
    os.kill(p.pid, signal.SIGINT)
    p.wait()
