from abc import ABC, abstractmethod

from fastapi import APIRouter, Depends
from jupyverse_api import Router, Config

from ..auth import Auth, User
from ..app import App


class ResourceUsage(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app)

        router = APIRouter()

        @router.get("/api/metrics/v1")
        async def get_metrics(
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ):
            return await self.get_metrics(user)

        self.include_router(router)

    @abstractmethod
    async def get_metrics(
        self,
        user: User,
    ):
        ...


class ResourceUsageConfig(Config):
    mem_limit: int = 0
    mem_warning_threshold: int = 0
    track_cpu_percent: bool = False
    cpu_limit: int = 0
    cpu_warning_threshold: int = 0
