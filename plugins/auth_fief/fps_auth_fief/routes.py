import json
from typing import Dict, List

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from fief_client import FiefAccessTokenInfo  # type: ignore
from jupyverse_api import Router
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User

from .backend import Backend
from .config import _AuthFiefConfig


class _AuthFief(Backend, Auth, Router):
    def __init__(
        self,
        app: App,
        auth_fief_config: _AuthFiefConfig,
    ) -> None:
        Router.__init__(self, app)
        Backend.__init__(self, auth_fief_config)

        router = APIRouter()

        @router.get("/auth-callback", name="auth_callback")
        async def auth_callback(request: Request, response: Response, code: str = Query(...)):
            redirect_uri = str(request.url_for("auth_callback"))
            tokens, _ = await self.fief.auth_callback(code, redirect_uri)

            response = RedirectResponse(request.url_for("root"))
            response.set_cookie(
                self.SESSION_COOKIE_NAME,
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
            access_token_info: FiefAccessTokenInfo = Depends(self.auth.authenticated()),
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
