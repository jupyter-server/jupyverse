from abc import ABC, abstractmethod
from typing import List

from fastapi import APIRouter, Depends
from jupyverse_api import Router

from .models import Terminal
from ..app import App
from ..auth import Auth, User


class Terminals(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

        @router.get("/api/terminals")
        async def get_terminals(
            user: User = Depends(auth.current_user({"terminals": ["read"]})),
        ) -> List[Terminal]:
            return await self.get_terminals(user)

        @router.post("/api/terminals")
        async def create_terminal(
            user: User = Depends(auth.current_user({"terminals": ["write"]})),
        ):
            return await self.create_terminal(user)

        @router.delete("/api/terminals/{name}", status_code=204)
        async def delete_terminal(
            name: str,
            user: User = Depends(auth.current_user(permissions={"terminals": ["write"]})),
        ):
            return await self.delete_terminal(name, user)

        @router.websocket("/terminals/websocket/{name}")
        async def terminal_websocket(
            name,
            websocket_permissions=Depends(
                auth.websocket_auth(permissions={"terminals": ["read", "execute"]})
            ),
        ):
            return await self.terminal_websocket(name, websocket_permissions)

        self.include_router(router)

    @abstractmethod
    async def get_terminals(
        self,
        user: User,
    ) -> List[Terminal]:
        ...

    @abstractmethod
    async def create_terminal(
        self,
        user: User,
    ):
        ...

    @abstractmethod
    async def delete_terminal(
        self,
        name: str,
        user: User,
    ):
        ...

    @abstractmethod
    async def terminal_websocket(
        self,
        name,
        websocket_permissions,
    ):
        ...


class TerminalServer(ABC):
    @abstractmethod
    async def serve(self, websocket, permissions):
        ...

    @abstractmethod
    def quit(self, websocket):
        ...
