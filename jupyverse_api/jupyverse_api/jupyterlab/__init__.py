from abc import ABC, abstractmethod

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from jupyverse_api import Config, Router

from ..auth import Auth, User
from ..app import App


class JupyterLab(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app)

        router = APIRouter()

        @router.get("/lab")
        async def get_lab(
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_lab(user)

        @router.get("/lab/tree/{path:path}")
        async def load_workspace(
            path,
        ):
            return await self.load_workspace(path)

        @router.get("/lab/api/workspaces/{name}")
        async def get_workspace_data(user: User = Depends(auth.current_user())):
            return await self.get_workspace_data(user)

        @router.put(
            "/lab/api/workspaces/{name}",
            status_code=204,
        )
        async def set_workspace(
            request: Request,
            user: User = Depends(auth.current_user()),
            user_update=Depends(auth.update_user),
        ):
            return await self.set_workspace(request, user, user_update)

        @router.get("/lab/workspaces/{name}", response_class=HTMLResponse)
        async def get_workspace(
            name,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_workspace(name, user)

        self.include_router(router)

    @abstractmethod
    async def get_lab(
        self,
        user: User,
    ):
        ...

    @abstractmethod
    async def load_workspace(
        self,
        path,
    ):
        ...

    @abstractmethod
    async def get_workspace_data(self, user: User):
        ...

    @abstractmethod
    async def set_workspace(
        self,
        request: Request,
        user: User,
        user_update,
    ):
        ...

    @abstractmethod
    async def get_workspace(
        self,
        name,
        user: User,
    ):
        ...


class JupyterLabConfig(Config):
    dev_mode: bool = False
