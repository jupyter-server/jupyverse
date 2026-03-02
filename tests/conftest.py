import os
import shutil
import signal
import subprocess
import time
from pathlib import Path

import pytest
import requests

HERE = Path(__file__).parent


@pytest.fixture
def anyio_backend():
    # at least, SQLAlchemy and pyzmq don't support anything else than asyncio
    return "asyncio"


@pytest.fixture()
def cwd():
    return Path(__file__).parents[1]


@pytest.fixture()
def tmp_cwd(tmp_path):
    prev_dir = Path.cwd()
    os.chdir(tmp_path)
    yield tmp_path
    os.chdir(prev_dir)


@pytest.fixture()
def start_jupyverse(auth_mode, clear_users, tmp_cwd, free_tcp_port):
    os.chdir(tmp_cwd)
    shutil.copytree(HERE / "data", "data")
    command_list = [
        "jupyverse",
        "--disable",
        "noauth",
        "--disable",
        "auth_fief",
        "--disable",
        "auth_jupyterhub",
        "--disable",
        "notebook",
        "--disable",
        "file_watcher_poll",
        "--set",
        f"auth.mode={auth_mode}",
        "--set",
        f"auth.clear_users={str(clear_users).lower()}",
        "--set",
        "kernels.require_yjs=true",
        "--port",
        str(free_tcp_port),
        "--timeout",
        "10",
    ]
    p = subprocess.Popen(command_list)
    url = f"http://127.0.0.1:{free_tcp_port}"
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
