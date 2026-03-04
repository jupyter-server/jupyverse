from abc import ABC, abstractmethod
from importlib.metadata import version

__version__ = version("jupyverse_file_id")


class FileId(ABC):
    @abstractmethod
    async def get_path(self, file_id: str) -> str | None: ...

    @abstractmethod
    async def get_id(self, file_path: str) -> str | None: ...

    @abstractmethod
    async def index(self, path: str) -> str | None: ...

    def watch(self, path: str): ...

    def unwatch(self, path: str, watcher): ...
