import json

import requests
import pytest


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (True,))
def test_settings_persistence_put(start_jupyverse):
    url = start_jupyverse
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data='{"raw":"my_settings"}',
    )
    assert response.status_code == 204


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_get(start_jupyverse):
    url = start_jupyverse
    response = requests.get(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
    )
    assert response.status_code == 200
    assert json.loads(response.content)["raw"] == "my_settings"
