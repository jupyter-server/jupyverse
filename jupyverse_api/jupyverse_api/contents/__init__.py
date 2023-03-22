import asyncio
from pathlib import Path
from typing import Dict, Union

from jupyverse_api import Router

from .models import Content, SaveContent


class FileIdManager:
    stop_watching_files: asyncio.Event
    stopped_watching_files: asyncio.Event

    async def get_path(self, file_id: str) -> str:
        raise RuntimeError("Not implemented")

    async def get_id(self, file_path: str) -> str:
        raise RuntimeError("Not implemented")


class Contents(Router):
    @property
    def file_id_manager(self) -> FileIdManager:
        raise RuntimeError("Not implemented")

    async def read_content(
        self, path: Union[str, Path], get_content: bool, as_json: bool = False
    ) -> Content:
        raise RuntimeError("Not implemented")

    async def write_content(self, content: Union[SaveContent, Dict]) -> None:
        raise RuntimeError("Not implemented")
