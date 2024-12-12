import json

import pytest
from fastaio import get_root_component, merge_config
from httpx import AsyncClient

test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}

CONFIG = {
    "jupyverse": {
        "type": "jupyverse_api.main:JupyverseComponent",
        "components": {
            "app": {
                "type": "jupyverse_api.main:AppComponent",
            },
            "auth": {
                "type": "fps_auth.main:AuthComponent",
                "config": {
                    "test": True,
                },
            },
            "contents": {
                "type": "fps_contents.main:ContentsComponent",
            },
            "frontend": {
                "type": "fps_frontend.main:FrontentComponent",
            },
            "lab": {
                "type": "fps_lab.main:LabComponent",
            },
            "jupyterlab": {
                "type": "fps_jupyterlab.main:JupyterlabComponent",
            },
            "kernels": {
                "type": "fps_kernels.main:KernelsComponent",
            },
            "yjs": {
                "type": "fps_yjs.main:YjsComponent",
            },
        }
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
                "components": {
                    "auth": {
                        "config": {
                            "mode": auth_mode,
                        }
                    }
                }
            }
        }
    )
    async with get_root_component(config), AsyncClient() as http:
        # get previous theme
        response = await http.get(
            f"http://127.0.0.1:{unused_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes"
        )
        assert response.status_code == 200
        theme = {"raw": json.loads(response.content)["raw"]}
        # put new theme
        response = await http.put(
            f"http://127.0.0.1:{unused_tcp_port}/lab/api/settings/@jupyterlab/apputils-extension:themes",
            data=json.dumps(test_theme),
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
            data=json.dumps(theme),
        )
        assert response.status_code == 204
