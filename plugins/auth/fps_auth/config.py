from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore
from pydantic import SecretStr
from typing import Literal


class AuthConfig(PluginModel):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    redirect_uri: str = ""
    mode: Literal["noauth", "token", "user"] = "token"
    cookie_secure: bool = (
        False  # FIXME: should default to True, and set to False for tests
    )
    clear_users: bool = False
    login_url: str = "/login_page"


def get_auth_config():
    return get_config(AuthConfig)


c = register_config(AuthConfig)
n = register_plugin_name("authenticator")
