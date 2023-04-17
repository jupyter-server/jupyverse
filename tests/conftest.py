import os
import subprocess
import time
from pathlib import Path

import pytest
import requests


@pytest.fixture()
def cwd():
    return Path(__file__).parents[1]


@pytest.fixture()
def start_jupyverse(auth_mode, clear_users, cwd, unused_tcp_port):
    os.chdir(cwd)
    command_list = [
        "asphalt",
        "run",
        "config.yaml",
        "--set",
        f"component.components.auth.mode={auth_mode}",
        "--set",
        f"component.components.auth.clear_users={str(clear_users).lower()}",
        "--set",
        "component.components.kernels.require_yjs=true",
        "--set",
        f"component.port={unused_tcp_port}",
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
    p.kill()
    p.wait()
