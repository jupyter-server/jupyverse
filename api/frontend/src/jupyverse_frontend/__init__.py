from importlib.metadata import version

from jupyverse_api import Config

__version__ = version("jupyverse_frontend")


class FrontendConfig(Config):
    base_url: str = "/"
    collaborative: bool = False
