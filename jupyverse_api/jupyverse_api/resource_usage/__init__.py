from jupyverse_api import Router, Config


class ResourceUsage(Router):
    pass


class ResourceUsageConfig(Config):
    mem_limit: int = 0
    mem_warning_threshold: int = 0
    track_cpu_percent: bool = False
    cpu_limit: int = 0
    cpu_warning_threshold: int = 0
