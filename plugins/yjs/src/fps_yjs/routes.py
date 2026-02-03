from uuid import uuid4

from fastapi import (
    HTTPException,
    Request,
    Response,
    status,
)
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.file_id import FileId
from jupyverse_api.yjs import Yjs
from jupyverse_api.yjs.models import CreateDocumentSession
from jupyverse_api.yroom import AsyncWebSocket, YRoom, YRoomManager
from pycrdt import Doc

from .widgets import Widgets

SERVER_SESSION = uuid4().hex


class _Yjs(Yjs):
    def __init__(
        self,
        app: App,
        auth: Auth,
        file_id: FileId,
        yroom_manager: YRoomManager,
    ) -> None:
        super().__init__(app=app, auth=auth)
        self.file_id = file_id
        self.yroom_manager = yroom_manager
        if Widgets is None:
            self.widgets = None
        else:
            self.widgets = Widgets()  # type: ignore

    async def collaboration_room_websocket(
        self,
        path,
        websocket_permissions,
    ):
        if websocket_permissions is None:
            return
        websocket, permissions = websocket_permissions
        await websocket.accept()
        ywebsocket = AsyncWebSocket(websocket, path)
        await self.yroom_manager.serve(ywebsocket, permissions)

    async def create_roomid(
        self,
        path,
        request: Request,
        response: Response,
        user: User,
    ):
        # we need to process the request manually
        # see https://github.com/tiangolo/fastapi/issues/3373#issuecomment-1306003451
        create_document_session = CreateDocumentSession(**(await request.json()))
        idx = await self.file_id.get_id(path)
        res = {
            "format": create_document_session.format,
            "type": create_document_session.type,
            "sessionId": SERVER_SESSION,
        }
        if idx is not None:
            res["fileId"] = idx
            return res

        idx = await self.file_id.index(path)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"File {path} does not exist")

        response.status_code = status.HTTP_201_CREATED
        res["fileId"] = idx
        return res

    async def get_room(self, id: str, doc: Doc | None = None) -> YRoom:
        return await self.yroom_manager.get_room(id, doc=doc)
