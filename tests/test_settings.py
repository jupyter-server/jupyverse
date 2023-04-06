import json

import pytest
from asphalt.core import Context
from httpx import AsyncClient
from jupyverse_api.main import JupyverseComponent

from utils import configure


test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}

COMPONENTS = {
    "app": {"type": "app"},
    "auth": {"type": "auth", "test": True},
    "contents": {"type": "contents"},
    "frontend": {"type": "frontend"},
    "lab": {"type": "lab"},
    "jupyterlab": {"type": "jupyterlab"},
    "kernels": {"type": "kernels"},
    "yjs": {"type": "yjs"},
}


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_settings(auth_mode, unused_tcp_port):
    components = configure(COMPONENTS, {"auth": {"mode": auth_mode}})
    async with Context() as ctx, AsyncClient() as http:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

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
