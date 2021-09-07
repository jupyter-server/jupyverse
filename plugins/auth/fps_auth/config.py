from fps.config import PluginModel  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore
from pydantic import SecretStr


class AuthConfig(PluginModel):
    client_id: str = ""
    client_secret: SecretStr = SecretStr("")
    redirect_uri: str = ""
    disable_auth: bool = False
    cookie_secure: bool = (
        False  # FIXME: should default to True, and set to False for tests
    )
    clear_users: bool = False


c = register_config(AuthConfig)
n = register_plugin_name("authenticator")
