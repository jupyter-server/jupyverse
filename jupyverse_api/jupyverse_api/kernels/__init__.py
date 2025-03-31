from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from fastapi import APIRouter, Depends, Request
from pydantic import Field

from jupyverse_api import Config, Router

from ..app import App
from ..auth import Auth, User
from .models import Session


class Kernels(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

        @router.get("/api/status")
        async def get_status(
            user: User = Depends(auth.current_user(permissions={"status": ["read"]})),
        ):
            return await self.get_status(user)

        @router.get("/api/kernelspecs")
        async def get_kernelspecs(
            user: User = Depends(auth.current_user(permissions={"kernelspecs": ["read"]})),
        ):
            return await self.get_kernelspecs(user)

        @router.get("/kernelspecs/{kernel_name}/{file_name}")
        async def get_kernelspec(
            kernel_name,
            file_name,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_kernelspec(kernel_name, file_name, user)

        @router.get("/api/kernels")
        async def get_kernels(
            user: User = Depends(auth.current_user(permissions={"kernels": ["read"]})),
        ):
            return await self.get_kernels(user)

        @router.delete("/api/sessions/{session_id}", status_code=204)
        async def delete_session(
            session_id: str,
            user: User = Depends(auth.current_user(permissions={"sessions": ["write"]})),
        ):
            return await self.delete_session(session_id, user)

        @router.patch("/api/sessions/{session_id}")
        async def rename_session(
            request: Request,
            user: User = Depends(auth.current_user(permissions={"sessions": ["write"]})),
        ) -> Session:
            return await self.rename_session(request, user)

        @router.get("/api/sessions")
        async def get_sessions(
            user: User = Depends(auth.current_user(permissions={"sessions": ["read"]})),
        ) -> list[Session]:
            return await self.get_sessions(user)

        @router.post(
            "/api/sessions",
            status_code=201,
            response_model=Session,
        )
        async def create_session(
            request: Request,
            user: User = Depends(auth.current_user(permissions={"sessions": ["write"]})),
        ) -> Session:
            return await self.create_session(request, user)

        @router.post("/api/kernels/{kernel_id}/interrupt")
        async def interrupt_kernel(
            kernel_id,
            user: User = Depends(auth.current_user(permissions={"kernels": ["write"]})),
        ):
            return await self.interrupt_kernel(kernel_id, user)

        @router.post("/api/kernels/{kernel_id}/restart")
        async def restart_kernel(
            kernel_id,
            user: User = Depends(auth.current_user(permissions={"kernels": ["write"]})),
        ):
            return await self.restart_kernel(kernel_id, user)

        @router.post("/api/kernels/{kernel_id}/execute")
        async def execute_cell(
            request: Request,
            kernel_id,
            user: User = Depends(auth.current_user(permissions={"kernels": ["write"]})),
        ):
            return await self.execute_cell(request, kernel_id, user)

        @router.get("/api/kernels/{kernel_id}")
        async def get_kernel(
            kernel_id,
            user: User = Depends(auth.current_user(permissions={"kernels": ["read"]})),
        ):
            return await self.get_kernel(kernel_id, user)

        @router.delete("/api/kernels/{kernel_id}", status_code=204)
        async def shutdown_kernel(
            kernel_id,
            user: User = Depends(auth.current_user(permissions={"kernels": ["write"]})),
        ):
            return await self.shutdown_kernel(kernel_id, user)

        @router.websocket("/api/kernels/{kernel_id}/channels")
        async def kernel_channels(
            kernel_id,
            session_id,
            websocket_permissions=Depends(
                auth.websocket_auth(permissions={"kernels": ["execute"]})
            ),
        ):
            return await self.kernel_channels(kernel_id, session_id, websocket_permissions)

        self.include_router(router)

    @abstractmethod
    async def watch_connection_files(self, path: Path) -> None: ...

    @abstractmethod
    async def get_status(
        self,
        user: User,
    ): ...

    @abstractmethod
    async def get_kernelspecs(
        self,
        user: User,
    ): ...

    @abstractmethod
    async def get_kernelspec(
        self,
        kernel_name,
        file_name,
        user: User,
    ): ...

    @abstractmethod
    async def get_kernels(
        self,
        user: User,
    ): ...

    @abstractmethod
    async def delete_session(
        self,
        session_id: str,
        user: User,
    ): ...

    @abstractmethod
    async def rename_session(
        self,
        request: Request,
        user: User,
    ) -> Session: ...

    @abstractmethod
    async def get_sessions(
        self,
        user: User,
    ) -> list[Session]: ...

    @abstractmethod
    async def create_session(
        self,
        request: Request,
        user: User,
    ) -> Session: ...

    @abstractmethod
    async def interrupt_kernel(
        self,
        kernel_id,
        user: User,
    ): ...

    @abstractmethod
    async def restart_kernel(
        self,
        kernel_id,
        user: User,
    ): ...

    @abstractmethod
    async def execute_cell(
        self,
        request: Request,
        kernel_id,
        user: User,
    ): ...

    @abstractmethod
    async def get_kernel(
        self,
        kernel_id,
        user: User,
    ): ...

    @abstractmethod
    async def shutdown_kernel(
        self,
        kernel_id,
        user: User,
    ): ...

    @abstractmethod
    async def kernel_channels(
        self,
        kernel_id,
        session_id,
        websocket_permissions,
    ): ...


class KernelsConfig(Config):
    default_kernel: str = "python3"
    allow_external_kernels: bool = Field(
        description=(
            "Whether or not to allow external kernels, whose connection files are placed in "
            "external_connection_dir."
        ),
        default=False,
    )
    external_connection_dir: str | None = Field(
        description=(
            "The directory to look at for external kernel connection files, if "
            "allow_external_kernels is True. Defaults to Jupyter runtime_dir/external_kernels. "
            "Make sure that this directory is not filled with left-over connection files."
        ),
        default=None,
    )
    require_yjs: bool = False
