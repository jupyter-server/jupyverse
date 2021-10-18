from uuid import uuid4
from typing import Literal, Optional
from pydantic import SecretStr

from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore


class AuthConfig(PluginModel):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    redirect_uri: str = ""
    mode: Literal["noauth", "token", "user"] = "token"
    token: str = str(uuid4())
    collaborative: bool = False
    global_email: str = "guest@jupyter.com"
    cookie_secure: bool = (
        False  # FIXME: should default to True, and set to False for tests
    )
    clear_users: bool = False
    login_url: Optional[str] = None


def get_auth_config():
    return get_config(AuthConfig)


c = register_config(AuthConfig)
n = register_plugin_name("authenticator")
