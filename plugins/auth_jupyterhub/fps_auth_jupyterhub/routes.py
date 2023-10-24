from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

import httpx
from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, WebSocket, status
from fastapi.responses import RedirectResponse
from jupyterhub.services.auth import HubOAuth
from jupyterhub.utils import isoformat
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing_extensions import Annotated

from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User

from .db import UserDB
from .models import JupyterHubUser


def auth_factory(
    app: App,
    db_session: AsyncSession,
    http_client: httpx.AsyncClient,
):
    class AuthJupyterHub(Auth, Router):
        def __init__(self) -> None:
            super().__init__(app)
            self.hub_auth = HubOAuth()
            self.db_lock = asyncio.Lock()
            self.activity_url = os.environ.get("JUPYTERHUB_ACTIVITY_URL")
            self.server_name = os.environ.get("JUPYTERHUB_SERVER_NAME")
            self.background_tasks = set()

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
                    db_session.add(
                        UserDB(
                            token=token,
                            name=hub_user["name"],
                            username=hub_user["name"],
                        ),
                    )
                    await db_session.commit()

                next_url = self.hub_auth.get_next_url(cookie_state)
                response = RedirectResponse(next_url)
                response.set_cookie(key="jupyverse_jupyterhub_token", value=token)
                return response

            @router.get("/api/me")
            async def get_api_me(
                request: Request,
                user: User = Depends(self.current_user()),
            ):
                checked_permissions: Dict[str, List[str]] = {}
                permissions = json.loads(
                    dict(request.query_params).get("permissions", "{}").replace("'", '"')
                )
                if permissions:
                    user_permissions: Dict[str, List[str]] = {}
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

        def current_user(self, permissions: Optional[Dict[str, List[str]]] = None) -> Callable:
            async def _(
                request: Request,
                jupyverse_jupyterhub_token: Annotated[Union[str, None], Cookie()] = None,
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
                        user_db = await db_session.scalar(
                            select(UserDB).filter_by(token=jupyverse_jupyterhub_token)
                        )
                    user = JupyterHubUser.model_validate(user_db)
                    if self.activity_url:
                        headers = {
                            "Authorization": f"token {self.hub_auth.api_token}",
                            "Content-Type": "application/json",
                        }
                        last_activity = isoformat(datetime.utcnow())
                        task = asyncio.create_task(
                            http_client.post(
                                self.activity_url,
                                headers=headers,
                                json={
                                    "servers": {self.server_name: {"last_activity": last_activity}}
                                },
                            )
                        )
                        self.background_tasks.add(task)
                        task.add_done_callback(self.background_tasks.discard)
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

        async def update_user(
            self, jupyverse_jupyterhub_token: Annotated[Union[str, None], Cookie()] = None
        ) -> Callable:
            async def _(data: Dict[str, Any]) -> JupyterHubUser:
                if jupyverse_jupyterhub_token is not None:
                    async with self.db_lock:
                        user_db = await db_session.scalar(
                            select(UserDB).filter_by(token=jupyverse_jupyterhub_token)
                        )
                        for k, v in data.items():
                            setattr(user_db, k, v)
                        await db_session.commit()
                    user = JupyterHubUser.model_validate(user_db)
                    return user

            return _

        def websocket_auth(
            self,
            permissions: Optional[Dict[str, List[str]]] = None,
        ) -> Callable[[], Tuple[Any, Dict[str, List[str]]]]:
            async def _(
                websocket: WebSocket,
            ) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
                accept_websocket = False
                if "jupyverse_jupyterhub_token" in websocket._cookies:
                    jupyverse_jupyterhub_token = websocket._cookies["jupyverse_jupyterhub_token"]
                    async with self.db_lock:
                        user_db = await db_session.scalar(
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
