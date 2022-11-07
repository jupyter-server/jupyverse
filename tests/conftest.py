import os
import socket
import subprocess
import time
from pathlib import Path

import pytest

pytest_plugins = (
    "fps.testing.fixtures",
    "fps_auth.fixtures",
)


@pytest.fixture()
def cwd():
    return Path(__file__).parents[1]


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
        f"--auth.mode={auth_mode}",
        "--auth.clear_users=" + str(clear_users).lower(),
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
