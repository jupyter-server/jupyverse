import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_kernel_subprocess")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
