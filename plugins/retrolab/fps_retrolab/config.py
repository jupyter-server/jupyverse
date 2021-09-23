from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore


class RetroLabConfig(PluginModel):
    base_url: str = "/"


def get_rlab_config():
    return get_config(RetroLabConfig)


c = register_config(RetroLabConfig)
n = register_plugin_name("RetroLab")
