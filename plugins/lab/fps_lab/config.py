from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config  # type: ignore


class LabConfig(PluginModel):
    collaborative: bool = False


def get_lab_config():
    return get_config(LabConfig)


c = register_config(LabConfig)
