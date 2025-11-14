from __future__ import annotations

from collections.abc import AsyncGenerator
from pathlib import Path

from anychange import awatch
from anyio import Event
from jupyverse_api.file_watcher import FileChange, FileWatcher


class _FileWatcher(FileWatcher):
    async def watch(  # type: ignore[override]
        self, path: Path | str,
        stop_event: Event | None = None,
    ) -> AsyncGenerator[set[FileChange], None]:
        async for changes in awatch(path, stop_event=stop_event):
            yield changes  # type: ignore[misc]
