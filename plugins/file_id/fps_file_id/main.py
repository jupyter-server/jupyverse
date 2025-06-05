from anyio import create_task_group
from fps import Module

from jupyverse_api.file_id import FileId

from .file_id import _FileId


class FileIdModule(Module):
    async def prepare(self) -> None:
        self.file_id = _FileId()

        async with create_task_group() as tg:
            tg.start_soon(self.file_id.start)
            self.put(self.file_id, FileId, teardown_callback=self.file_id.stop)
            self.done()
