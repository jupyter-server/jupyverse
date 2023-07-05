from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import Depends, HTTPException, Request, Response, WebSocket, status
from fastapi.security import APIKeyCookie
from fief_client import FiefAccessTokenInfo, FiefAsync, FiefUserInfo
from fief_client.integrations.fastapi import FiefAuth
from jupyverse_api.auth import User

from .config import _AuthFiefConfig


@dataclass
class Res:
    fief: FiefAsync
    session_cookie_name: str
    auth: FiefAuth
    current_user: Any
    update_user: Any
    websocket_auth: Any


def get_backend(auth_fief_config: _AuthFiefConfig) -> Res:
    class CustomFiefAuth(FiefAuth):
        client: FiefAsync

        async def get_unauthorized_response(self, request: Request, response: Response):
            if auth_fief_config.callback_url:
                redirect_uri = auth_fief_config.callback_url
            else:
                redirect_uri = str(request.url_for("auth_callback"))
            auth_url = await self.client.auth_url(redirect_uri, scope=["openid", "offline_access"])
            raise HTTPException(
                status_code=status.HTTP_307_TEMPORARY_REDIRECT,
                headers={"Location": auth_url},
            )

    fief = FiefAsync(
        auth_fief_config.base_url,
        auth_fief_config.client_id,
        auth_fief_config.client_secret,
    )

    session_cookie_name = "fps_auth_fief_user_session"
    scheme = APIKeyCookie(name=session_cookie_name, auto_error=False)
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
            if session_cookie_name in websocket._cookies:
                access_token = websocket._cookies[session_cookie_name]
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

        async def _(
            user: FiefUserInfo = Depends(auth.current_user(permissions=permissions)),
        ):
            return User(**user["fields"])

        return _

    return Res(
        fief=fief,
        session_cookie_name=session_cookie_name,
        auth=auth,
        current_user=current_user,
        update_user=update_user,
        websocket_auth=websocket_auth,
    )
