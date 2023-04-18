from abc import ABC, abstractmethod

from fastapi import APIRouter
from jupyverse_api import Router

from ..app import App


class Login(Router, ABC):
    def __init__(self, app: App):
        super().__init__(app)

        router = APIRouter()

        @router.get("/login")
        async def get_login():
            return await self.get_login()

        self.include_router(router)

    @abstractmethod
    async def get_login(self):
        ...
