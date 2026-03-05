from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import IntEnum
from importlib.metadata import version
from pathlib import Path

from anyio import Event

__version__ = version("jupyverse_file_watcher")


class Change(IntEnum):
    added = 1
    modified = 2
    deleted = 3


FileChange = tuple[Change, str]


class FileWatcher(ABC):
    @abstractmethod
    async def watch(
        self,
        path: Path | str,
        stop_event: Event | None = None,
    ) -> AsyncGenerator[set[FileChange], None]: ...
