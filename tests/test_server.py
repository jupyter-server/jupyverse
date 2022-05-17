import json

import pytest
import requests

prev_theme = {}
test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_put(start_jupyverse):
    url = start_jupyverse
    # get previous theme
    response = requests.get(url + "/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    prev_theme["raw"] = json.loads(response.content)["raw"]
    # put new theme
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes", data=json.dumps(test_theme)
    )
    assert response.status_code == 204


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_get(start_jupyverse):
    url = start_jupyverse
    # get new theme
    response = requests.get(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
    )
    assert response.status_code == 200
    assert json.loads(response.content)["raw"] == test_theme["raw"]
    # put previous theme back
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data=json.dumps(prev_theme),
    )
    assert response.status_code == 204
