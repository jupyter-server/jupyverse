from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException, Request, Response, WebSocket, status
from fastapi.security import APIKeyCookie
from fief_client import FiefAccessTokenInfo, FiefAsync, FiefUserInfo
from fief_client.integrations.fastapi import FiefAuth

from .config import get_auth_fief_config
from .models import UserRead


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

SESSION_COOKIE_NAME = "fps_auth_fief_user_session"
scheme = APIKeyCookie(name=SESSION_COOKIE_NAME, auto_error=False)
auth = CustomFiefAuth(fief, scheme)


async def update_user(
    user: FiefUserInfo = Depends(auth.current_user()),
    access_token_info: FiefAccessTokenInfo = Depends(auth.authenticated()),
):
    async def _(data: Dict[str, Any]) -> FiefUserInfo:
        user = await fief.update_profile(access_token_info["access_token"], {"fields": data})
        return user

    return _


def websocket_auth(permissions: Optional[Dict[str, List[str]]] = None):
    async def _(
        websocket: WebSocket,
    ) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
        accept_websocket = False
        checked_permissions: Optional[Dict[str, List[str]]] = None
        if SESSION_COOKIE_NAME in websocket._cookies:
            access_token = websocket._cookies[SESSION_COOKIE_NAME]
            if permissions is None:
                accept_websocket = True
            else:
                checked_permissions = {}
                for resource, actions in permissions.items():
                    allowed = checked_permissions[resource] = []
                    for action in actions:
                        try:
                            await fief.validate_access_token(
                                access_token, required_permissions=[f"{resource}:{action}"]
                            )
                        except BaseException:
                            pass
                        else:
                            allowed.append(action)
                            accept_websocket = True
        if accept_websocket:
            return websocket, checked_permissions
        else:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

    return _


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
