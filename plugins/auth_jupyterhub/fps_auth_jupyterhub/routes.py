from __future__ import annotations

import json
import os
from collections.abc import Awaitable
from datetime import datetime
from functools import partial
from typing import Annotated, Any, Callable

from anyio import TASK_STATUS_IGNORED, Lock, create_task_group, sleep
from anyio.abc import TaskStatus
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, WebSocket, status
from fastapi.responses import RedirectResponse
from httpx import AsyncClient
from jupyterhub.services.auth import HubOAuth
from jupyterhub.utils import isoformat
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.future import select

from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User

from .config import AuthJupyterHubConfig
from .db import Base, UserDB
from .models import JupyterHubUser


def auth_factory(
    app: App,
    auth_jupyterhub_config: AuthJupyterHubConfig,
):
    class AuthJupyterHub(Auth, Router):
        def __init__(self) -> None:
            super().__init__(app)
            self.db_engine = create_async_engine(auth_jupyterhub_config.db_url)
            self.db_session = AsyncSession(self.db_engine)

            self.http_client = AsyncClient()
            self.hub_auth = HubOAuth()
            self.db_lock = Lock()
            self.activity_url = os.environ.get("JUPYTERHUB_ACTIVITY_URL")
            self.server_name = os.environ.get("JUPYTERHUB_SERVER_NAME")
            self.http_client = AsyncClient()

            router = APIRouter()

            @router.get("/oauth_callback")
            async def get_oauth_callback(
                request: Request,
                code: str | None = None,
                state: str | None = None,
            ):
                if code is None:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

                cookie_state = request.cookies.get(self.hub_auth.state_cookie_name)
                if state is None or state != cookie_state:
                    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

                token = self.hub_auth.token_for_code(code)
                hub_user = await self.hub_auth.user_for_token(token, use_cache=False, sync=False)
                async with self.db_lock:
                    self.db_session.add(
                        UserDB(
                            token=token,
                            name=hub_user["name"],
                            username=hub_user["name"],
                        ),
                    )
                    await self.db_session.commit()

                next_url = self.hub_auth.get_next_url(cookie_state)
                response = RedirectResponse(next_url)
                response.set_cookie(key="jupyverse_jupyterhub_token", value=token)
                return response

            @router.get("/api/me")
            async def get_api_me(
                request: Request,
                user: User = Depends(self.current_user()),
            ):
                checked_permissions: dict[str, list[str]] = {}
                permissions = json.loads(
                    dict(request.query_params).get("permissions", "{}").replace("'", '"')
                )
                if permissions:
                    user_permissions: dict[str, list[str]] = {}
                    for resource, actions in permissions.items():
                        user_resource_permissions = user_permissions.get(resource, [])
                        allowed = checked_permissions[resource] = []
                        for action in actions:
                            if action in user_resource_permissions:
                                allowed.append(action)

                keys = ["username", "name", "display_name", "initials", "avatar_url", "color"]
                identity = {k: getattr(user, k) for k in keys}
                return {
                    "identity": identity,
                    "permissions": checked_permissions,
                }

            self.include_router(router)

        def current_user(self, permissions: dict[str, list[str]] | None = None) -> Callable:
            async def _(
                request: Request,
                jupyverse_jupyterhub_token: Annotated[str | None, Cookie()] = None,
            ):
                if jupyverse_jupyterhub_token is not None:
                    hub_user = await self.hub_auth.user_for_token(
                        jupyverse_jupyterhub_token, use_cache=False, sync=False
                    )
                    scopes = self.hub_auth.check_scopes(self.hub_auth.access_scopes, hub_user)
                    if not scopes:
                        raise HTTPException(
                            status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"User {hub_user['name']} cannot access this server",
                        )

                    async with self.db_lock:
                        user_db = await self.db_session.scalar(
                            select(UserDB).filter_by(token=jupyverse_jupyterhub_token)
                        )
                    user = JupyterHubUser.model_validate(user_db)
                    if self.activity_url:
                        headers = {
                            "Authorization": f"token {self.hub_auth.api_token}",
                            "Content-Type": "application/json",
                        }
                        last_activity = isoformat(datetime.utcnow())
                        self.task_group.start_soon(
                            partial(
                                self.http_client.post,
                                self.activity_url,
                                headers=headers,
                                json={
                                    "servers": {self.server_name: {"last_activity": last_activity}}
                                },
                            )
                        )
                    return user

                if permissions:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                    )

                state = self.hub_auth.generate_state(next_url=str(request.url))
                raise HTTPException(
                    status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                    headers={
                        "Location": f"{self.hub_auth.login_url}&state={state}",
                        "Set-Cookie": f"{self.hub_auth.state_cookie_name}={state}",
                    },
                )

            return _

        async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
            async with self.db_engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

            async with create_task_group() as tg:
                self.task_group = tg
                task_status.started()
                await sleep(float("inf"))

        async def stop(self) -> None:
            await self.http_client.aclose()
            await self.db_session.close()
            await self.db_engine.dispose()
            self.task_group.cancel_scope.cancel()

        async def update_user(
            self, jupyverse_jupyterhub_token: Annotated[str | None, Cookie()] = None
        ) -> Callable:
            async def _(data: dict[str, Any]) -> JupyterHubUser | None:
                if jupyverse_jupyterhub_token is not None:
                    async with self.db_lock:
                        user_db = await self.db_session.scalar(
                            select(UserDB).filter_by(token=jupyverse_jupyterhub_token)
                        )
                        for k, v in data.items():
                            setattr(user_db, k, v)
                        await self.db_session.commit()
                    user = JupyterHubUser.model_validate(user_db)
                    return user
                return None

            return _

        def websocket_auth(
            self,
            permissions: dict[str, list[str]] | None = None,
        ) -> Callable[[Any], Awaitable[tuple[Any, dict[str, list[str]] | None] | None]]:
            async def _(
                websocket: WebSocket,
            ) -> tuple[Any, dict[str, list[str]] | None] | None:
                accept_websocket = False
                if "jupyverse_jupyterhub_token" in websocket._cookies:
                    jupyverse_jupyterhub_token = websocket._cookies["jupyverse_jupyterhub_token"]
                    async with self.db_lock:
                        user_db = await self.db_session.scalar(
                            select(UserDB).filter_by(token=jupyverse_jupyterhub_token)
                        )
                    if user_db:
                        accept_websocket = True
                if accept_websocket:
                    return websocket, permissions
                else:
                    await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                    return None

            return _

    return AuthJupyterHub()
