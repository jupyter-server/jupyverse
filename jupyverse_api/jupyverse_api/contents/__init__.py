from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from anyioutils import ResourceLock
from fastapi import APIRouter, Depends, Request, Response

from jupyverse_api import Router

from ..app import App
from ..auth import Auth, User
from .models import Checkpoint, Content, SaveContent


class Contents(Router, ABC):
    file_lock: ResourceLock

    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)
        self.file_lock = ResourceLock()
        router = APIRouter()

        @router.post(
            "/api/contents/{path:path}/checkpoints",
            status_code=201,
        )
        async def create_checkpoint(
            path, user: User = Depends(auth.current_user(permissions={"contents": ["write"]}))
        ) -> Checkpoint:
            return await self.create_checkpoint(path, user)

        @router.post(
            "/api/contents{path:path}",
            status_code=201,
        )
        async def create_content(
            path: str | None,
            request: Request,
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
        ) -> Content:
            return await self.create_content(path, request, user)

        @router.get("/api/contents")
        async def get_root_content(
            content: int,
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ) -> Content:
            return await self.get_root_content(content, user)

        @router.get("/api/contents/{path:path}/checkpoints")
        async def get_checkpoint(
            path, user: User = Depends(auth.current_user(permissions={"contents": ["read"]}))
        ) -> list[Checkpoint]:
            return await self.get_checkpoint(path, user)

        @router.get("/api/contents/{path:path}")
        async def get_content(
            path: str,
            content: int = 0,
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ) -> Content:
            return await self.get_content(path, content, user)

        @router.put("/api/contents/{path:path}")
        async def save_content(
            path,
            request: Request,
            response: Response,
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
        ) -> Content:
            return await self.save_content(path, request, response, user)

        @router.delete(
            "/api/contents/{path:path}",
            status_code=204,
        )
        async def delete_content(
            path,
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
        ):
            return await self.delete_content(path, user)

        @router.patch("/api/contents/{path:path}")
        async def rename_content(
            path,
            request: Request,
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
        ) -> Content:
            return await self.rename_content(path, request, user)

        self.include_router(router)

    @abstractmethod
    async def read_content(
        self, path: str | Path, get_content: bool, file_format: str | None = None
    ) -> Content: ...

    @abstractmethod
    async def write_content(self, content: SaveContent | dict) -> None: ...

    @abstractmethod
    async def create_checkpoint(
        self,
        path,
        user: User,
    ) -> Checkpoint: ...

    @abstractmethod
    async def create_content(
        self,
        path: str | None,
        request: Request,
        user: User,
    ) -> Content: ...

    @abstractmethod
    async def get_root_content(
        self,
        content: int,
        user: User,
    ) -> Content:
        return await self.get_root_content(content, user)

    @abstractmethod
    async def get_checkpoint(
        self,
        path,
        user: User,
    ) -> list[Checkpoint]: ...

    @abstractmethod
    async def get_content(
        self,
        path: str,
        content: int,
        user: User,
    ) -> Content: ...

    @abstractmethod
    async def save_content(
        self,
        path,
        request: Request,
        response: Response,
        user: User,
    ) -> Content: ...

    @abstractmethod
    async def delete_content(
        self,
        path,
        user: User,
    ): ...

    @abstractmethod
    async def rename_content(
        self,
        path,
        request: Request,
        user: User,
    ) -> Content: ...
