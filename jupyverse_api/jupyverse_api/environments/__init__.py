from __future__ import annotations

from abc import ABC, abstractmethod

from fastapi import APIRouter, Depends

from jupyverse_api import Router

from ..app import App
from ..auth import Auth, User
from .models import CreateEnvironment, Environment, EnvironmentStatus


class Environments(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

        @router.delete("/api/environments/{environment_id}", status_code=204)
        async def delete_environment(
            environment_id: str,
            user: User = Depends(auth.current_user(permissions={"sessions": ["write"]})),
        ):
            return await self.delete_environment(environment_id, user)

        @router.post(
            "/api/environments",
            status_code=201,
            response_model=Environment,
        )
        async def create_environment(
            environment: CreateEnvironment,
            user: User = Depends(auth.current_user(permissions={"sessions": ["write"]})),
        ) -> Environment:
            return await self.create_environment(environment, user)

        @router.get("/api/environments/wait/{environment_id}")
        async def wait_for_environment(environment_id: str) -> None:
            return await self.wait_for_environment(environment_id)

        @router.get("/api/environments/status/{environment_id}")
        async def get_status(id: str) -> EnvironmentStatus:
            return await self.get_status(id)

        self.include_router(router)

    @abstractmethod
    async def delete_environment(
        self,
        id: str,
        user: User,
    ) -> None: ...

    @abstractmethod
    async def create_environment(
        self,
        environment: CreateEnvironment,
        user: User,
    ) -> Environment: ...

    @abstractmethod
    async def wait_for_environment(self, id: str) -> None: ...

    @abstractmethod
    async def get_status(self, id: str) -> EnvironmentStatus: ...

    @abstractmethod
    async def run_in_environment(self, id: str, command: str) -> int: ...

    @abstractmethod
    def add_package_manager(self, name: str, package_manager: PackageManager): ...


class PackageManager(ABC):
    @abstractmethod
    async def create_environment(self, environment_file_path: str) -> str: ...

    @abstractmethod
    async def delete_environment(self, id: str) -> None: ...

    @abstractmethod
    async def wait_for_environment(self, id: str) -> None: ...

    @abstractmethod
    async def get_status(self, id: str) -> EnvironmentStatus: ...

    @abstractmethod
    async def run_in_environment(self, id: str, command: str) -> int: ...
