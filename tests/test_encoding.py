import subprocess
import sys
import warnings
from pathlib import Path

import anyio
from fps import get_root_module
from fps_kernel_subprocess.connect import read_connection_file, write_connection_file
from httpx2 import ASGITransport, AsyncClient

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "config": {
            "start_server": False,
        },
        "modules": {
            "app": {
                "type": "app",
            },
            "auth": {
                "type": "auth",
                "config": {
                    "test": True,
                    "mode": "noauth",
                },
            },
            "contents": {
                "type": "contents",
            },
            "file_watcher": {
                "type": "file_watcher",
            },
            "frontend": {
                "type": "frontend",
            },
            "page_config": {
                "type": "page_config",
            },
            "lab": {
                "type": "lab",
            },
            "jupyterlab": {
                "type": "jupyterlab",
            },
            "kernel_subprocess": {
                "type": "kernel_subprocess",
            },
            "kernels": {
                "type": "kernels",
            },
            "nbconvert": {
                "type": "nbconvert",
            },
        },
    }
}

TEXT = "café, 日本語"


def test_utf8_file_io(tmp_path):
    # EncodingWarning is only emitted if warn_default_encoding is set at startup,
    # so main() runs in a new interpreter.
    process = subprocess.run(
        [sys.executable, "-X", "warn_default_encoding", __file__], cwd=tmp_path, timeout=50
    )
    assert process.returncode == 0


async def main():
    # Fail on text file I/O in jupyverse that falls back to the locale encoding (#557).
    # anyio.Path and anyio.open_file call open() in a worker thread,
    # so their warnings are attributed to anyio.
    warnings.filterwarnings("error", category=EncodingWarning, module="fps_|jupyverse|anyio")

    async with get_root_module(CONFIG) as root_module:
        transport = ASGITransport(app=root_module.app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            response = await client.get("/lab/api/settings")
            assert response.status_code == 200
            response = await client.get("/lab/api/settings/@jupyterlab/running-extension:plugin")
            assert response.status_code == 200

            response = await client.get("/api/kernelspecs")
            assert response.status_code == 200

            response = await client.post("/api/contents", json={"type": "notebook", "path": ""})
            assert response.status_code == 201
            response = await client.post(
                "/api/contents", json={"type": "file", "ext": ".txt", "path": ""}
            )
            assert response.status_code == 201

            content = {"type": "file", "format": "text", "path": "file.txt", "content": TEXT}
            response = await client.put("/api/contents/file.txt", json=content)
            assert response.status_code == 200
            assert Path("file.txt").read_bytes() == TEXT.encode("utf-8")
            response = await client.get("/api/contents/file.txt")
            assert response.status_code == 200
            assert response.json()["content"] == TEXT

            notebook = {
                "cells": [{"cell_type": "markdown", "id": "0", "metadata": {}, "source": TEXT}],
                "metadata": {},
                "nbformat": 4,
                "nbformat_minor": 5,
            }
            content = {
                "type": "notebook",
                "format": "json",
                "path": "notebook.ipynb",
                "content": notebook,
            }
            response = await client.put("/api/contents/notebook.ipynb", json=content)
            assert response.status_code == 200
            response = await client.get(
                "/nbconvert/html/notebook.ipynb", params={"download": False}
            )
            assert response.status_code == 200
            assert TEXT in response.text

    connection_file, cfg = write_connection_file()
    assert read_connection_file(connection_file) == cfg
    Path(connection_file).unlink()


if __name__ == "__main__":
    anyio.run(main)
