from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config  # type: ignore


class FrontendConfig(PluginModel):
    base_url: str = "/"


def get_frontend_config():
    return get_config(FrontendConfig)


c = register_config(FrontendConfig)
