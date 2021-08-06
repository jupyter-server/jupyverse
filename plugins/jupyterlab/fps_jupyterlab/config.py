from fps.config import PluginModel  # type: ignore
from fps.hooks import register_config, register_plugin_name  # type: ignore


class JupyterLabConfig(PluginModel):
    collaborative: bool = False


c = register_config(JupyterLabConfig)
n = register_plugin_name("JupyterLab")
