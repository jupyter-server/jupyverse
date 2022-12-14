from fps.config import PluginModel, get_config  # type: ignore
from fps.hooks import register_config  # type: ignore
from pydantic import BaseSettings  # type: ignore


class ResourceUsageConfig(PluginModel, BaseSettings):
    mem_limit: int = 0
    mem_warning_threshold: int = 0
    track_cpu_percent: bool = False
    cpu_limit: int = 0
    cpu_warning_threshold: int = 0


def get_resource_usage_config():
    return get_config(ResourceUsageConfig)


c = register_config(ResourceUsageConfig)
