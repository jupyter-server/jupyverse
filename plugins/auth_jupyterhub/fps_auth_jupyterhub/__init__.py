import importlib.metadata

from .launch import launch  # noqa

try:
    __version__ = importlib.metadata.version("fps_auth_jupyterhub")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
