from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

from fastapi import APIRouter, Depends, Request
from jupyverse_api import Router, Config

from ..app import App
from ..auth import Auth, User
from .models import Session


class Kernels(Router, ABC):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

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
        ) -> List[Session]:
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
    async def watch_connection_files(self, path: Path) -> None:
        ...

    @abstractmethod
    async def get_kernelspecs(
        self,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_kernelspec(
        self,
        kernel_name,
        file_name,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_kernels(
        self,
        user: User,
    ):
        ...

    @abstractmethod
    async def delete_session(
        self,
        session_id: str,
        user: User,
    ):
        ...

    @abstractmethod
    async def rename_session(
        self,
        request: Request,
        user: User,
    ) -> Session:
        ...

    @abstractmethod
    async def get_sessions(
        self,
        user: User,
    ) -> List[Session]:
        ...

    @abstractmethod
    async def create_session(
        self,
        request: Request,
        user: User,
    ) -> Session:
        ...

    @abstractmethod
    async def interrupt_kernel(
        self,
        kernel_id,
        user: User,
    ):
        ...

    @abstractmethod
    async def restart_kernel(
        self,
        kernel_id,
        user: User,
    ):
        ...

    @abstractmethod
    async def execute_cell(
        self,
        request: Request,
        kernel_id,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_kernel(
        self,
        kernel_id,
        user: User,
    ):
        ...

    @abstractmethod
    async def shutdown_kernel(
        self,
        kernel_id,
        user: User,
    ):
        ...

    @abstractmethod
    async def kernel_channels(
        self,
        kernel_id,
        session_id,
        websocket_permissions,
    ):
        ...


class KernelsConfig(Config):
    default_kernel: str = "python3"
    connection_path: Optional[str] = None
    require_yjs: bool = False
