from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

from jupyverse_api import Router, Config


class Kernels(Router, ABC):
    @abstractmethod
    async def watch_connection_files(self, path: Path) -> None:
        ...


class KernelsConfig(Config):
    default_kernel: str = "python3"
    connection_path: Optional[str] = None
