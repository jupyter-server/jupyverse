from anyio import create_task_group
from fps import Module
from jupyverse_api.file_id import FileId
from jupyverse_api.file_watcher import FileWatcher

from .file_id import _FileId


class FileIdModule(Module):
    async def prepare(self) -> None:
        file_watcher = await self.get(FileWatcher)  # type: ignore[type-abstract]
        self.file_id = _FileId(file_watcher)

        async with create_task_group() as tg:
            tg.start_soon(self.file_id.start)
            self.put(self.file_id, FileId, teardown_callback=self.file_id.stop)
            self.done()
