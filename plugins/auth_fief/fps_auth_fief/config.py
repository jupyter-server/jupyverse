from fps.config import PluginModel, get_config
from fps.hooks import register_config
from pydantic import BaseSettings, SecretStr


class AuthFiefConfig(PluginModel, BaseSettings):
    base_url: str  # Base URL of Fief tenant
    client_id: str  # ID of Fief client
    client_secret: SecretStr  # Secret of Fief client

    class Config(PluginModel.Config):
        env_prefix = "fps_auth_fief_"
        # config can be set with environment variables, e.g.:
        # export FPS_AUTH_FIEF_BASE_URL=https://jupyverse.fief.dev
        # export FPS_AUTH_FIEF_CLIENT_ID=my_client_id
        # export FPS_AUTH_FIEF_CLIENT_SECRET=my_client_secret


def get_auth_fief_config():
    return get_config(AuthFiefConfig)


c = register_config(AuthFiefConfig)
