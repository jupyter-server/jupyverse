from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from pathlib import Path

import structlog
from anyio import Event
from jupyverse_api.file_watcher import FileChange, FileWatcher
from watchfiles import awatch

logger = structlog.get_logger()
watchfiles_logger = logging.getLogger("watchfiles")
watchfiles_logger.setLevel(logging.WARNING)


class _FileWatcher(FileWatcher):
    async def watch(  # type: ignore[override]
        self,
        path: Path | str,
        stop_event: Event | None = None,
    ) -> AsyncGenerator[set[FileChange], None]:
        async for changes in awatch(path, stop_event=stop_event):
            yield changes  # type: ignore[misc]
