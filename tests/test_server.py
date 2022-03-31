import json

import pytest
import requests

theme = {"raw": None}


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_put(start_jupyverse):
    url = start_jupyverse
    # get previous theme
    response = requests.get(url + "/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    theme["raw"] = json.loads(response.content)["raw"]
    # put new theme
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data='{"raw": "{// jupyverse test\\n\\"theme\\": \\"JupyterLab Dark\\"}"}',
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
    assert json.loads(response.content)["raw"] == '{// jupyverse test\n"theme": "JupyterLab Dark"}'
    # put previous theme back
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data=json.dumps(theme),
    )
    assert response.status_code == 204
