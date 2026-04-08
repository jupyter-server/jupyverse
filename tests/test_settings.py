import json
import shutil
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


@pytest.fixture
def fake_scoped_extension():
    ext_dir = Path(sys.prefix) / "share" / "jupyter" / "labextensions" / "@my-org" / "my-extension"
    schema_dir = ext_dir / "schemas" / "@my-org" / "my-extension"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "package.json").write_text(
        json.dumps({"name": "@my-org/my-extension", "version": "1.2.3"})
    )
    (schema_dir / "plugin.json").write_text(
        json.dumps(
            {
                "title": "My Extension",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        )
    )
    yield ext_dir
    shutil.rmtree(Path(sys.prefix) / "share" / "jupyter" / "labextensions" / "@my-org")


@pytest.fixture
def fake_flat_extension():
    ext_dir = Path(sys.prefix) / "share" / "jupyter" / "labextensions" / "my-extension"
    schema_dir = ext_dir / "schemas" / "my-extension"
    schema_dir.mkdir(parents=True, exist_ok=True)
    (ext_dir / "package.json").write_text(json.dumps({"name": "my-extension", "version": "2.0.0"}))
    (schema_dir / "plugin.json").write_text(
        json.dumps(
            {
                "title": "My Extension",
                "type": "object",
                "properties": {},
                "additionalProperties": False,
            }
        )
    )
    yield ext_dir
    shutil.rmtree(ext_dir)


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_scoped_extension_setting(auth_mode, fake_scoped_extension, free_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": free_tcp_port},
                "modules": {"auth": {"config": {"mode": auth_mode}}},
            }
        },
    )
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with root_module, AsyncClient() as http:
        response = await http.get(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/@my-org/my-extension:plugin"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "@my-org/my-extension:plugin"
        assert data["version"] == "1.2.3"


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_flat_extension_setting(auth_mode, fake_flat_extension, free_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": free_tcp_port},
                "modules": {"auth": {"config": {"mode": auth_mode}}},
            }
        },
    )
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with root_module, AsyncClient() as http:
        response = await http.get(
            f"http://127.0.0.1:{free_tcp_port}/lab/api/settings/my-extension:plugin"
        )
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "my-extension:plugin"
        assert data["version"] == "2.0.0"


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
