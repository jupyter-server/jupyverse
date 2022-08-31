from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config  # type: ignore


class JupyterLabConfig(PluginModel):
    dev_mode: bool = False


def get_jlab_config():
    return get_config(JupyterLabConfig)


c = register_config(JupyterLabConfig)
