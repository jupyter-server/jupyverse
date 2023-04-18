from abc import ABC, abstractmethod

from fastapi import APIRouter, Depends
from jupyverse_api import Router

from ..app import App
from ..auth import Auth, User


class Nbconvert(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app)

        router = APIRouter()

        @router.get("/api/nbconvert")
        async def get_nbconvert_formats():
            return await self.get_nbconvert_formats()

        @router.get("/nbconvert/{format}/{path}")
        async def get_nbconvert_document(
            format: str,
            path: str,
            download: bool,
            user: User = Depends(auth.current_user(permissions={"nbconvert": ["read"]})),
        ):
            return await self.get_nbconvert_document(format, path, download, user)

        self.include_router(router)

    @abstractmethod
    async def get_nbconvert_formats(self):
        ...

    @abstractmethod
    async def get_nbconvert_document(
        self,
        format: str,
        path: str,
        download: bool,
        user: User,
    ):
        ...
