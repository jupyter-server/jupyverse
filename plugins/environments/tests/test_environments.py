import json
import platform

import httpx
import pytest
from anyio import fail_after, sleep
from fps import get_root_module

from jupyverse_api.environments import Environments

ENVIRONMENT = """\
name: my-test-env
dependencies:
  - numpy
  - ipykernel
"""


@pytest.mark.anyio
@pytest.mark.skipif(platform.system() == "Windows", reason="Doesn't support Windows")
async def test_kernel_environment_micromamba(tmp_path):
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
                    "type": "noauth",
                },
                "environment_micromamba": {
                    "type": "environment_micromamba",
                },
                "environments": {
                    "type": "environments",
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
        environments = await root_module.get(Environments)
        app = root_module.app
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as client:
            environment_file_path = tmp_path / "environment.yml"
            environment_file_path.write_text(ENVIRONMENT)
            data = {
                "package_manager_name": "micromamba",
                "environment_file_path": str(environment_file_path),
            }
            r = await client.post("/api/environments", json=data)
            assert r.status_code == 201
            response = r.json()
            assert response["status"] == "environment creation start"
            environment_id = response["id"]
            r = await client.get(f"/api/environments/wait/{environment_id}")
            assert r.status_code == 200
            data = {
                "name": "Untitled.ipynb",
                "path": "012-abc",
                "type": "notebook",
                "kernel": {
                    "name": "python3",
                    "environment_id": environment_id,
                },
            }
            r = await client.post("/api/sessions", content=json.dumps(data))
            assert r.status_code == 201
            test_file_path = tmp_path / "foo.txt"
            code_file_path = tmp_path / "foo.py"
            code_file_path.write_text("import numpy; print(numpy)")
            cmd = f"python {code_file_path} > {test_file_path}"
            await environments.run_in_environment(environment_id, cmd)
            with fail_after(1):
                while True:
                    await sleep(0.1)
                    if test_file_path.is_file():
                        content = test_file_path.read_text()
                        if content:
                            assert content.startswith("<module 'numpy' from ")
                            break
            r = await client.delete(f"/api/environments/{environment_id}")
            assert r.status_code == 204
