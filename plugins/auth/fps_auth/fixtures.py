import pytest  # type: ignore
from fps_auth.config import AuthConfig, get_auth_config


@pytest.fixture
def auth_mode():
    return "token"


@pytest.fixture
def auth_config(auth_mode):
    yield AuthConfig.parse_obj({"mode": auth_mode})


@pytest.fixture
def config_override(app, auth_config):
    async def override_get_config():
        return auth_config

    app.dependency_overrides[get_auth_config] = override_get_config
