from importlib.metadata import version

from .lab import Lab as Lab
from .page_config import PageConfig as PageConfig
from .page_config import PageConfigModule as PageConfigModule

__version__ = version(__package__)
