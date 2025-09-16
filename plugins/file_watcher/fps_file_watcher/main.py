from fps import Module
from jupyverse_api.file_watcher import FileWatcher

from .file_watcher import _FileWatcher


class FileWatcherModule(Module):
    async def prepare(self) -> None:
        file_watcher = _FileWatcher()
        self.put(file_watcher, FileWatcher)
