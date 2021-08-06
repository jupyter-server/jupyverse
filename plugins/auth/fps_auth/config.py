from pydantic import SecretStr

from fps.config import PluginModel  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore


class AuthConfig(PluginModel):
    client_id: str = ""
    client_secret: SecretStr = ""
    redirect_uri: str = ""


c = register_config(AuthConfig)
n = register_plugin_name("authenticator")
