from fps import Module
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.file_id import FileId
from jupyverse_api.yjs import Yjs
from jupyverse_api.yroom import YRoomManager

from .routes import _Yjs


class YjsModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        file_id = await self.get(FileId)  # type: ignore[type-abstract]
        yroom_manager = await self.get(YRoomManager)

        yjs = _Yjs(app, auth, file_id, yroom_manager)
        self.put(yjs, Yjs)
