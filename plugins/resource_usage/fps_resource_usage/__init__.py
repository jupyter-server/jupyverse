import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_resource_usage")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
