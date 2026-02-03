from functools import partial
from typing import Any

from fps import Module
from jupyverse_api.contents import Contents
from jupyverse_api.file_id import FileId
from jupyverse_api.yroom import YRoomFactory, YRoomManager
from jupyverse_api.ystore import YStoreFactory

from .config import YRoomConfig
from .yroom import _YRoom, _YRoomManager


class YRoomModule(Module):
    def __init__(self, name: str, **kwargs: Any):
        super().__init__(name)
        self.config = YRoomConfig(**kwargs)

    async def prepare(self) -> None:
        contents = await self.get(Contents)  # type: ignore[type-abstract]
        file_id = await self.get(FileId)  # type: ignore[type-abstract]
        ystore_factory = await self.get(YStoreFactory)
        yroom_factory = YRoomFactory(
            partial(_YRoom, contents, file_id, ystore_factory, self.config)  # type: ignore[arg-type]
        )
        yroom_manager = _YRoomManager(yroom_factory)
        async with yroom_manager as yroom_manager:
            self.put(yroom_manager, YRoomManager)
            self.done()
            await self.started.wait()
            await self.freed(yroom_manager)
