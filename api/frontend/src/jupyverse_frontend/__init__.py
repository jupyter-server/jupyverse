from importlib.metadata import version

from jupyverse_api import Config

__version__ = version(__package__)


class FrontendConfig(Config):
    base_url: str = "/"
    collaborative: bool = False
