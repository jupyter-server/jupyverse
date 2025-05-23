import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_login")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
