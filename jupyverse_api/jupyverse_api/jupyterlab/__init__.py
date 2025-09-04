from abc import ABC, abstractmethod

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse

from jupyverse_api import Config, Router

from ..app import App
from ..auth import Auth, User


class JupyterLab(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app)

        router = APIRouter()

        @router.get("/lab")
        async def get_lab(
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_lab("lab", user)

        @router.get("/doc")
        async def get_doc(
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_lab("doc", user)

        @router.get("/{mode}/tree/{path:path}")
        async def load_workspace(
            mode,
            path,
        ):
            if mode not in {"lab", "doc"}:
                raise HTTPException(status_code=404, detail="Not found")
            return await self.load_workspace(mode, path)

        @router.get("/lab/api/workspaces/{name}")
        @router.get("/doc/api/workspaces/{name}")
        async def get_workspace_data(user: User = Depends(auth.current_user())):
            return await self.get_workspace_data(user)

        @router.put(
            "/lab/api/workspaces/{name}",
            status_code=204,
        )
        @router.put(
            "/doc/api/workspaces/{name}",
            status_code=204,
        )
        async def set_workspace(
            request: Request,
            user: User = Depends(auth.current_user()),
            user_update=Depends(auth.update_user),
        ):
            return await self.set_workspace(request, user, user_update)

        @router.get("/{mode}/workspaces/{name}", response_class=HTMLResponse)
        async def get_workspace(
            mode,
            name,
            user: User = Depends(auth.current_user()),
        ):
            if mode not in {"lab", "doc"}:
                raise HTTPException(status_code=404, detail="Not found")

            return await self.get_workspace(mode, name, "", user)

        @router.get("/{mode}/workspaces/{name}/tree/{path:path}", response_class=HTMLResponse)
        async def get_workspace_with_tree(
            mode,
            name,
            path,
            user: User = Depends(auth.current_user()),
        ):
            if mode not in {"lab", "doc"}:
                raise HTTPException(status_code=404, detail="Not found")

            return await self.get_workspace(mode, name, path, user)

        self.include_router(router)

    @abstractmethod
    async def get_lab(
        self,
        mode,
        user: User,
    ): ...

    @abstractmethod
    async def load_workspace(
        self,
        mode,
        path,
    ): ...

    @abstractmethod
    async def get_workspace_data(self, user: User): ...

    @abstractmethod
    async def set_workspace(
        self,
        request: Request,
        user: User,
        user_update,
    ): ...

    @abstractmethod
    async def get_workspace(
        self,
        mode,
        name,
        path,
        user: User,
    ): ...


class JupyterLabConfig(Config):
    dev_mode: bool = False
    server_side_execution: bool = False
