import json
import sys

import pytest

test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.skipif(
    sys.platform.startswith(("linux", "darwin")) and sys.version_info < (3, 8),
    reason="pytest-asyncio issue",
)
def test_settings(client):
    # get previous theme
    response = client.get("/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    theme = {"raw": json.loads(response.content)["raw"]}
    # put new theme
    response = client.put(
        "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data=json.dumps(test_theme),
    )
    assert response.status_code == 204
    # get new theme
    response = client.get("/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    assert json.loads(response.content)["raw"] == test_theme["raw"]
    # put previous theme back
    response = client.put(
        "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data=json.dumps(theme),
    )
    assert response.status_code == 204
