import json

import pytest
from fps import get_root_module, merge_config
from httpx import AsyncClient

test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "modules": {
            "app": {
                "type": "app",
            },
            "auth": {
                "type": "auth",
                "config": {
                    "test": True,
                },
            },
            "contents": {
                "type": "contents",
            },
            "file_id": {
                "type": "file_id",
            },
            "frontend": {
                "type": "frontend",
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
            "yjs": {
                "type": "yjs",
            },
        },
    }
}


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_settings(auth_mode, unused_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": unused_tcp_port},
                "modules": {
                    "auth": {
                        "config": {
                            "mode": auth_mode,
                        }
                    }
                },
            }
        },
    )
    async with get_root_module(config), AsyncClient() as http:
        # get previous theme
        response = await http.get(
            f"http://127.0.0.1:{unused_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
        )
        assert response.status_code == 200
        theme = {"raw": json.loads(response.content)["raw"]}
        # put new theme
        response = await http.put(
            f"http://127.0.0.1:{unused_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes",
            content=json.dumps(test_theme),
        )
        assert response.status_code == 204
        # get new theme
        response = await http.get(
            f"http://127.0.0.1:{unused_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
        )
        assert response.status_code == 200
        assert json.loads(response.content)["raw"] == test_theme["raw"]
        # put previous theme back
        response = await http.put(
            f"http://127.0.0.1:{unused_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes",
            content=json.dumps(theme),
        )
        assert response.status_code == 204
