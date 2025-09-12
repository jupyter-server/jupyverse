import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_environment_micromamba")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
