import importlib.metadata

try:
    __version__ = importlib.metadata.version("fps_file_id")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"
