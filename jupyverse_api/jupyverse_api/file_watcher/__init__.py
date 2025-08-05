from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator
from enum import IntEnum
from pathlib import Path

from anyio import Event


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
