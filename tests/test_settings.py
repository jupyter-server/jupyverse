import json

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_put_settings(auth_mode, client, app):
    with TestClient(app) as client:
        response = client.put(
            "/lab/api/settings/@jupyterlab/apputils-extension:themes",
            data='{"raw":"my_settings"}',
        )
    assert response.status_code == 204


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_get_settings(auth_mode, client, app):
    with TestClient(app) as client:
        response = client.get("/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    assert json.loads(response.content)["raw"] == "my_settings"
