from typing import Optional
from uuid import uuid4

from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config  # type: ignore
from pydantic import BaseSettings, SecretStr


class AuthConfig(PluginModel, BaseSettings):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    redirect_uri: str = ""
    # mode: Literal["noauth", "token", "user"] = "token"
    mode: str = "token"
    token: str = str(uuid4())
    global_email: str = "guest@jupyter.com"
    cookie_secure: bool = False  # FIXME: should default to True, and set to False for tests
    clear_users: bool = False
    test: bool = False
    login_url: Optional[str] = None

    class Config(PluginModel.Config):
        env_prefix = "fps_auth_"


def get_auth_config():
    return get_config(AuthConfig)


c = register_config(AuthConfig)
