from fps import Module
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.file_id import FileId
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs
from jupyverse_api.yrooms import YRoomFactory, YRooms

from .routes import _Yjs


class YjsModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        file_id = await self.get(FileId)  # type: ignore[type-abstract]
        yroom_factory = await self.get(YRoomFactory)
        lifespan = await self.get(Lifespan)

        async with YRooms(yroom_factory, lifespan.shutdown_request) as yrooms:
            yjs = _Yjs(app, auth, file_id, yrooms)
            self.put(yjs, Yjs)
            self.done()
