from typing import Any, Dict, List, Optional

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    WebSocket,
    status,
)
from fastapi.responses import RedirectResponse
from fastapi.security import APIKeyCookie
from fief_client import FiefAccessTokenInfo, FiefAsync, FiefUserInfo
from fief_client.integrations.fastapi import FiefAuth
from fps.hooks import register_router
from pydantic import BaseModel

from .config import get_auth_fief_config


class CustomFiefAuth(FiefAuth):
    client: FiefAsync

    async def get_unauthorized_response(self, request: Request, response: Response):
        redirect_uri = request.url_for("auth_callback")
        auth_url = await self.client.auth_url(redirect_uri, scope=["openid"])
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": auth_url},
        )


auth_fief_config = get_auth_fief_config()

fief = FiefAsync(
    auth_fief_config.base_url,
    auth_fief_config.client_id,
    auth_fief_config.client_secret.get_secret_value(),
)

SESSION_COOKIE_NAME = "user_session"
scheme = APIKeyCookie(name=SESSION_COOKIE_NAME, auto_error=False)
auth = CustomFiefAuth(fief, scheme)


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


async def update_user(
    user: FiefUserInfo = Depends(auth.current_user()),
    access_token_info: FiefAccessTokenInfo = Depends(auth.authenticated()),
):
    async def _(data: Dict[str, Any]) -> FiefUserInfo:
        user = await fief.update_profile(access_token_info["access_token"], {"fields": data})
        print(f"{user=}")
        return user

    return _


def websocket_auth(permissions: Optional[Dict[str, List[str]]] = None):
    async def _(
        websocket: WebSocket,
    ) -> Optional[WebSocket]:
        return websocket

    return _


r = register_router(router)


class UserRead(BaseModel):
    workspace: str = "{}"
    settings: str = "{}"


def current_user(permissions=None):
    if permissions is not None:
        permissions = [
            f"{resource}:{action}"
            for resource, actions in permissions.items()
            for action in actions
        ]

    async def _(user: FiefUserInfo = Depends(auth.current_user(permissions=permissions))):
        return UserRead(**user["fields"])

    return _
