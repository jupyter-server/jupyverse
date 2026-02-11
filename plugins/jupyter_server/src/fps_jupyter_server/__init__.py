import importlib.metadata

from .jupyter_server import JupyterServer as JupyterServer

try:
    __version__ = importlib.metadata.version("fps_jupyter_server")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
