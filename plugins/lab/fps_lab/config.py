from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore


class LabConfig(PluginModel):
    collaborative: bool = False
    base_url: str = "/"


def get_lab_config():
    return get_config(LabConfig)


c = register_config(LabConfig)
n = register_plugin_name("Lab")
