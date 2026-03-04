from functools import partial
from typing import Any

from fps import Module
from jupyverse_contents import Contents
from jupyverse_file_id import FileId
from jupyverse_yrooms import YRoomFactory
from jupyverse_ystore import YStoreFactory

from .config import YRoomsConfig
from .yrooms import YRoom


class YRoomsModule(Module):
    def __init__(self, name: str, **kwargs: Any):
        super().__init__(name)
        self.config = YRoomsConfig(**kwargs)

    async def prepare(self) -> None:
        contents = await self.get(Contents)  # type: ignore[type-abstract]
        file_id = await self.get(FileId)  # type: ignore[type-abstract]
        ystore_factory = await self.get(YStoreFactory)
        yroom_factory = YRoomFactory(
            partial(YRoom, contents, file_id, ystore_factory, self.config)  # type: ignore[arg-type]
        )
        self.put(yroom_factory)
