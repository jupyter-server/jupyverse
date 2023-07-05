import json
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from fief_client import FiefAccessTokenInfo
from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User

from .backend import get_backend
from .config import _AuthFiefConfig


def auth_factory(
    app: App,
    auth_fief_config: _AuthFiefConfig,
):
    backend = get_backend(auth_fief_config)

    class _AuthFief(Auth, Router):
        def __init__(self) -> None:
            super().__init__(app)

            router = APIRouter()

            @router.get("/auth-callback", name="auth_callback")
            async def auth_callback(
                request: Request,
                response: Response,
                code: str = Query(...),
            ):
                if auth_fief_config.callback_url:
                    redirect_uri = auth_fief_config.callback_url
                else:
                    redirect_uri = str(request.url_for("auth_callback"))
                tokens, user_info = await backend.fief.auth_callback(code, redirect_uri)

                user_id = user_info["sub"]
                async with httpx.AsyncClient() as client:
                    headers = {"Authorization": f"Bearer {auth_fief_config.admin_api_key}"}
                    r = await client.get(
                        f"{auth_fief_config.base_url}/admin/api/oauth-providers/{auth_fief_config.oauth_provider_id}/access-token/{user_id}",
                        headers=headers,
                    )

                # FIXME: this is hard-coded for GitHub authentication
                access_token = r.json()["access_token"]
                async with httpx.AsyncClient() as client:
                    headers = {
                        "Authorization": f"Bearer {access_token}",
                        "Accept": "application/vnd.github+json",
                        "X-GitHub-Api-Version": "2022-11-28",
                    }
                    r = await client.get("https://api.github.com/user", headers=headers)

                d = r.json()
                data = {
                    "username": d["login"],
                    "name": d["name"],
                    "display_name": d["name"],
                    "initials": "".join([word[0] for word in d["name"].split()]),
                    "avatar_url": d["avatar_url"],
                }
                await backend.fief.update_profile(tokens["access_token"], {"fields": data})

                # set permissions
                async with httpx.AsyncClient() as client:
                    headers = {
                        "Authorization": f"Bearer {auth_fief_config.admin_api_key}",
                        "accept": "application/json",
                    }
                    skip = 0
                    nb = 100
                    count = None
                    got = 0
                    while True:
                        params = {"limit": nb, "skip": skip}
                        r = await client.get(
                            f"{auth_fief_config.base_url}/admin/api/permissions/",
                            headers=headers,
                            params=params,
                        )
                        d = r.json()
                        if count is None:
                            count = d["count"]

                        permission_id = {
                            result["codename"]: result["id"] for result in d["results"]
                        }

                        headers = {"Authorization": f"Bearer {auth_fief_config.admin_api_key}"}
                        for permission, id in permission_id.items():
                            data = {"id": id}
                            await client.post(
                                f"{auth_fief_config.base_url}/admin/api/users/{user_id}/permissions",
                                headers=headers,
                                json=data,
                            )

                        got += len(d["results"])
                        if got < count:
                            skip += nb
                        else:
                            break

                refresh_token = tokens["refresh_token"]
                assert refresh_token is not None
                tokens, user_info = await backend.fief.auth_refresh_token(refresh_token)

                response = RedirectResponse(request.url_for("root"))
                response.set_cookie(
                    backend.session_cookie_name,
                    tokens["access_token"],
                    max_age=tokens["expires_in"],
                    httponly=True,
                    secure=False,
                )

                return response

            @router.get("/api/me")
            async def get_api_me(
                request: Request,
                user: User = Depends(self.current_user()),
                access_token_info: FiefAccessTokenInfo = Depends(backend.auth.authenticated()),
            ):
                checked_permissions: Dict[str, List[str]] = {}
                permissions = json.loads(
                    dict(request.query_params).get("permissions", "{}").replace("'", '"')
                )
                if permissions:
                    user_permissions: Dict[str, List[str]] = {}
                    for permission in access_token_info["permissions"]:
                        resource, action = permission.split(":")
                        if resource not in user_permissions:
                            user_permissions[resource] = []
                        user_permissions[resource].append(action)
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
            return backend.current_user(permissions)

        async def update_user(self, update_user=Depends(backend.update_user)) -> Callable:
            return update_user

        def websocket_auth(
            self,
            permissions: Optional[Dict[str, List[str]]] = None,
        ) -> Callable[[], Tuple[Any, Dict[str, List[str]]]]:
            return backend.websocket_auth(permissions)

    return _AuthFief()
