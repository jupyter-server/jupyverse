import json
import sys
from pathlib import Path

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
            "yjs": {
                "type": "yjs",
            },
            "yrooms": {
                "type": "yrooms",
            },
            "ystore_sqlite": {
                "type": "ystore_sqlite",
            },
        },
    }
}


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_settings(auth_mode, free_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": free_tcp_port},
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
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with root_module, AsyncClient() as http:
        overrides_dir = Path(sys.prefix) / "share" / "jupyter" / "lab" / "settings"
        overrides_dir.mkdir(exist_ok=True)
        overrides_path = overrides_dir / "overrides.json"
        overrides_path.unlink(missing_ok=True)
        # get previous theme
        response = await http.get(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
        )
        assert response.status_code == 200
        theme = {"raw": json.loads(response.content)["raw"]}
        # put new theme
        response = await http.put(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes",
            content=json.dumps(test_theme),
        )
        assert response.status_code == 204
        # get new theme
        response = await http.get(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
        )
        assert response.status_code == 200
        assert json.loads(response.content)["raw"] == test_theme["raw"]
        # write other theme in overrides.json
        overrides_path.write_text(
            json.dumps({"@jupyterlab/apputils-extension:themes": {"theme": "JupyterLab Other"}})
        )
        # get other theme
        response = await http.get(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
        )
        assert response.status_code == 200
        assert json.loads(json.loads(response.content)["raw"]) == {"theme": "JupyterLab Other"}
        overrides_path.unlink()
        # put previous theme back
        response = await http.put(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes",
            content=json.dumps(theme),
        )
        assert response.status_code == 204
