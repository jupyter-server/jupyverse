import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, Union

from jupyverse_api import Router

from .models import Content, SaveContent


class FileIdManager(ABC):
    stop_watching_files: asyncio.Event
    stopped_watching_files: asyncio.Event

    @abstractmethod
    async def get_path(self, file_id: str) -> str:
        ...

    @abstractmethod
    async def get_id(self, file_path: str) -> str:
        ...


class Contents(Router, ABC):
    @property
    @abstractmethod
    def file_id_manager(self) -> FileIdManager:
        ...

    @abstractmethod
    async def read_content(
        self, path: Union[str, Path], get_content: bool, as_json: bool = False
    ) -> Content:
        ...

    @abstractmethod
    async def write_content(self, content: Union[SaveContent, Dict]) -> None:
        ...
