from abc import ABCMeta, abstractmethod
from pathlib import Path
from typing import Dict, Union

from jupyverse_api import Router

from .models import Content, SaveContent


class Contents(Router, metaclass=ABCMeta):
    @abstractmethod
    def file_id_manager(self):
        ...

    @abstractmethod
    async def read_content(
        path: Union[str, Path], get_content: bool, as_json: bool = False
    ) -> Content:
        ...

    @abstractmethod
    async def write_content(self, content: Union[SaveContent, Dict]) -> None:
        ...
