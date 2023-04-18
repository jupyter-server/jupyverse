from abc import ABC, abstractmethod

from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from jupyverse_api import Router

from ..app import App
from ..auth import Auth, User
from ..lab import Lab


class RetroLab(Router, ABC):
    def __init__(self, app: App, auth: Auth, lab: Lab):
        super().__init__(app=app)

        router = APIRouter()

        @router.get("/retro/tree", response_class=HTMLResponse)
        async def get_tree(
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_tree(user)

        @router.get("/retro/notebooks/{path:path}", response_class=HTMLResponse)
        async def get_notebook(
            path,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_notebook(path, user)

        @router.get("/retro/edit/{path:path}", response_class=HTMLResponse)
        async def edit_file(
            path,
            user: User = Depends(auth.current_user()),
        ):
            return await self.edit_file(path, user)

        @router.get("/retro/consoles/{path:path}", response_class=HTMLResponse)
        async def get_console(
            path,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_console(path, user)

        @router.get("/retro/terminals/{name}", response_class=HTMLResponse)
        async def get_terminal(
            name: str,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_terminal(name, user)

        self.include_router(router)

    @abstractmethod
    async def get_tree(
        self,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_notebook(
        self,
        path,
        user: User,
    ):
        ...

    @abstractmethod
    async def edit_file(
        self,
        path,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_console(
        self,
        path,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_terminal(
        self,
        name: str,
        user: User,
    ):
        ...
