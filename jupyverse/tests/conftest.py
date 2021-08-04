import pytest

from fastapi.testclient import TestClient

from jupyverse import Jupyverse


@pytest.fixture()
def client():
    jupyverse = Jupyverse(
        open_browser=False,
        routers="jupyverse.routers.retro_lab,"
        "jupyverse.routers.contents,"
        "jupyverse.routers.kernels,",
    )
    return TestClient(jupyverse.app)
