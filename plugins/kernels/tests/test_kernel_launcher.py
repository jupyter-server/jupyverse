import json

import httpx
import pytest
from fps import get_root_module


@pytest.mark.anyio
@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_kernel_launcher():
    config = {
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
                "kernel_subprocess": {
                    "type": "kernel_subprocess",
                },
                "frontend": {
                    "type": "frontend",
                },
                "kernels": {
                    "type": "kernels",
                },
                "file_watcher": {
                    "type": "file_watcher",
                },
            },
        }
    }

    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with root_module as root_module:
        app = root_module.app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            data = {
                "name": "Untitled.ipynb",
                "path": "012-abc",
                "type": "notebook",
                "kernel": {
                    "name": "python3",
                },
            }
            r = await client.post("/api/sessions", content=json.dumps(data))
            assert r.status_code == 201
