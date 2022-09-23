from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import RedirectResponse
from fief_client import FiefAccessTokenInfo
from fps.hooks import register_router

from .backend import SESSION_COOKIE_NAME, auth, current_user, fief
from .models import Permissions, UserRead

router = APIRouter()


@router.get("/auth-callback", name="auth_callback")
async def auth_callback(request: Request, response: Response, code: str = Query(...)):
    redirect_uri = request.url_for("auth_callback")
    tokens, _ = await fief.auth_callback(code, redirect_uri)

    response = RedirectResponse(request.url_for("root"))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        tokens["access_token"],
        max_age=tokens["expires_in"],
        httponly=True,
        secure=False,
    )

    return response


@router.get("/api/me")
async def get_api_me(
    permissions_to_check: Optional[Permissions] = None,
    user: UserRead = Depends(current_user()),
    access_token_info: FiefAccessTokenInfo = Depends(auth.authenticated()),
):
    checked_permissions: Dict[str, List[str]] = {}
    if permissions_to_check is not None:
        permissions = permissions_to_check.permissions
        user_permissions = {}
        for permission in access_token_info["permissions"]:
            resource, action = permission.split(":")
            if resource not in user_permissions.keys():
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


r = register_router(router)
