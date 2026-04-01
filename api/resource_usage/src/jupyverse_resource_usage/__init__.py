from abc import ABC, abstractmethod
from importlib.metadata import version

from fastapi import APIRouter, Depends
from jupyverse_api import App, Config, Router
from jupyverse_auth import Auth, User

__version__ = version(__package__)


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
    ): ...


class ResourceUsageConfig(Config):
    mem_limit: int = 0
    mem_warning_threshold: float = 0.0
    track_cpu_percent: bool = False
    cpu_limit: int = 0
    cpu_warning_threshold: float = 0.0
