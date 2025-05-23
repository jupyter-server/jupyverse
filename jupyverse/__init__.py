import importlib.metadata

try:
    __version__ = importlib.metadata.version("jupyverse")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
