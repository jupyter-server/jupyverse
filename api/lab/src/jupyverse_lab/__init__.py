from importlib.metadata import version

from .lab import Lab as Lab
from .page_config import PageConfig as PageConfig
from .page_config import PageConfigModule as PageConfigModule
from .static import StaticScript as StaticScript
from .static import parse_static_scripts as parse_static_scripts

__version__ = version(__package__)
