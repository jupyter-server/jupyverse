from typing import Optional
from pathlib import Path

from jupyverse_api import Router, Config


class Kernels(Router):
    async def watch_connection_files(self, path: Path) -> None:
        raise RuntimeError("Not implemented")


class KernelsConfig(Config):
    default_kernel: str = "python3"
    connection_path: Optional[str] = None
