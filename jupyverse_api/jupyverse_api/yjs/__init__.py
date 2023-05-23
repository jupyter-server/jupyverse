from abc import ABC, abstractmethod
from typing import Any

from fastapi import APIRouter, Depends, Request, Response
from jupyverse_api import Router

from ..auth import Auth, User
from ..app import App


class Yjs(Router, ABC):
    websocket_server: Any

    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

        @router.websocket("/api/collaboration/room/{path:path}")
        async def collaboration_room_websocket(
            path,
            websocket_permissions=Depends(
                auth.websocket_auth(permissions={"yjs": ["read", "write"]})
            ),
        ):
            return await self.collaboration_room_websocket(path, websocket_permissions)

        @router.put("/api/collaboration/session/{path:path}", status_code=200)
        async def create_roomid(
            path,
            request: Request,
            response: Response,
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ):
            return await self.create_roomid(path, request, response, user)

        self.include_router(router)

    @abstractmethod
    async def collaboration_room_websocket(
        self,
        path,
        websocket_permissions,
    ):
        ...

    @abstractmethod
    async def create_roomid(
        self,
        path,
        request: Request,
        response: Response,
        user: User,
    ):
        ...

    @abstractmethod
    def get_document(
        self,
        document_id: str,
    ):
        ...
