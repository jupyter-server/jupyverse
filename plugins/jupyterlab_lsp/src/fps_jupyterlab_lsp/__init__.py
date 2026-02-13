import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_jupyterlab_lsp")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
