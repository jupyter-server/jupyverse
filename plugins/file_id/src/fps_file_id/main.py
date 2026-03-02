from anyio import Event
from fps import Module
from jupyverse_api.file_id import FileId
from jupyverse_api.file_watcher import FileWatcher
from pydantic import Field

from jupyverse_api import Config

from .file_id import _FileId


class FileIdModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = FileIdConfig(**kwargs)

    async def prepare(self) -> None:
        file_watcher = await self.get(FileWatcher)  # type: ignore[type-abstract]
        self._stop0_event = Event()
        self._stop1_event = Event()

        async with _FileId(file_watcher, self.config.db_path, self._stop0_event) as file_id:
            self.put(file_id, FileId)
            self.done()

        self._stop1_event.set()

    async def stop(self) -> None:
        self._stop0_event.set()
        await self._stop1_event.wait()


class FileIdConfig(Config):
    db_path: str = Field(
        description="The path to the SQLite database.",
        default=".fileid.db",
    )
