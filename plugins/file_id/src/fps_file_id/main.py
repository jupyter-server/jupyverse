from anyio import Event
from fps import Module
from jupyverse_api import Config
from jupyverse_file_id import FileId
from jupyverse_file_watcher import FileWatcher
from pydantic import Field

from .file_id import _FileId


class FileIdModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = FileIdConfig(**kwargs)

    async def prepare(self) -> None:
        file_watcher = await self.get(FileWatcher)  # type: ignore[type-abstract]
        self._stop_event0 = Event()
        self._stop_event1 = Event()

        async with _FileId(file_watcher, self.config.db_path, self._stop_event0) as file_id:
            self.put(file_id, FileId)
            self.done()

        self._stop_event1.set()

    async def stop(self) -> None:
        self._stop_event0.set()
        await self._stop_event1.wait()


class FileIdConfig(Config):
    db_path: str = Field(
        description="The path to the SQLite database.",
        default=".fileid.db",
    )
