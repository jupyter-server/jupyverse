import asyncio
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Union

from fastapi import APIRouter, Depends, Request, Response
from jupyverse_api import Router

from .models import Checkpoint, Content, SaveContent
from ..auth import Auth, User
from ..app import App


class FileIdManager(ABC):
    stop_watching_files: asyncio.Event
    stopped_watching_files: asyncio.Event

    @abstractmethod
    async def get_path(self, file_id: str) -> str:
        ...

    @abstractmethod
    async def get_id(self, file_path: str) -> str:
        ...

    def watch(self, path: str):
        ...

    def unwatch(self, path: str, watcher):
        ...


class Contents(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

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
            path: Optional[str],
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
        ) -> List[Checkpoint]:
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

    @property
    @abstractmethod
    def file_id_manager(self) -> FileIdManager:
        ...

    @abstractmethod
    async def read_content(
        self, path: Union[str, Path], get_content: bool, file_format: Optional[str] = None
    ) -> Content:
        ...

    @abstractmethod
    async def write_content(self, content: Union[SaveContent, Dict]) -> None:
        ...

    @abstractmethod
    async def create_checkpoint(
        self,
        path,
        user: User,
    ) -> Checkpoint:
        ...

    @abstractmethod
    async def create_content(
        self,
        path: Optional[str],
        request: Request,
        user: User,
    ) -> Content:
        ...

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
    ) -> List[Checkpoint]:
        ...

    @abstractmethod
    async def get_content(
        self,
        path: str,
        content: int,
        user: User,
    ) -> Content:
        ...

    @abstractmethod
    async def save_content(
        self,
        path,
        request: Request,
        response: Response,
        user: User,
    ) -> Content:
        ...

    @abstractmethod
    async def delete_content(
        self,
        path,
        user: User,
    ):
        ...

    @abstractmethod
    async def rename_content(
        self,
        path,
        request: Request,
        user: User,
    ) -> Content:
        ...
