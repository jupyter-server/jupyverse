import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_kernel_web_worker")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
