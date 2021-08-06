from fps.config import PluginModel
from fps.hooks import register_config, register_plugin_name


class JupyterLabConfig(PluginModel):
    collaborative: bool = False


c = register_config(JupyterLabConfig)
n = register_plugin_name("JupyterLab")
