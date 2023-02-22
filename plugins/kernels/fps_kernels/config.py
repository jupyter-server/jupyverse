from typing import Optional

from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config  # type: ignore


class KernelConfig(PluginModel):
    default_kernel: str = "python3"
    connection_path: Optional[str] = None


def get_kernel_config():
    return get_config(KernelConfig)


c = register_config(KernelConfig)
