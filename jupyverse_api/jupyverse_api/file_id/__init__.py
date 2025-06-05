from __future__ import annotations

from abc import ABC, abstractmethod


class FileId(ABC):
    @abstractmethod
    async def start(self) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def get_path(self, file_id: str) -> str | None: ...

    @abstractmethod
    async def get_id(self, file_path: str) -> str | None: ...

    @abstractmethod
    async def index(self, path: str) -> str | None: ...

    def watch(self, path: str): ...

    def unwatch(self, path: str, watcher): ...
