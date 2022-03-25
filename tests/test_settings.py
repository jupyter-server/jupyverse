import json
import sys

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.skipif(
    sys.platform.startswith(("linux", "darwin")) and sys.version_info < (3, 8),
    reason="pytest-asyncio issue",
)
def test_settings(client, app):
    with TestClient(app) as client:
        # get previous theme
        response = client.get("/lab/api/settings/@jupyterlab/apputils-extension:themes")
        assert response.status_code == 200
        theme = {"raw": json.loads(response.content)["raw"]}
        # put new theme
        response = client.put(
            "/lab/api/settings/@jupyterlab/apputils-extension:themes",
            data='{"raw": "{// jupyverse test\\n\\"theme\\": \\"JupyterLab Dark\\"}"}',
        )
        assert response.status_code == 204
        # get new theme
        response = client.get("/lab/api/settings/@jupyterlab/apputils-extension:themes")
        assert response.status_code == 200
        assert (
            json.loads(response.content)["raw"]
            == '{// jupyverse test\n"theme": "JupyterLab Dark"}'
        )
        # put previous theme back
        response = client.put(
            "/lab/api/settings/@jupyterlab/apputils-extension:themes",
            data=json.dumps(theme),
        )
        assert response.status_code == 204
