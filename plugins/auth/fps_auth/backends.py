import logging
import uuid
from dataclasses import dataclass
from typing import Any, Dict, Generic, List, Optional, Tuple

import httpx
from fastapi import Depends, HTTPException, Response, WebSocket, status
from fastapi_users import (
    BaseUserManager,
    FastAPIUsers,
    UUIDIDMixin,
    models,
)
from fastapi_users.authentication import (
    AuthenticationBackend,
    CookieTransport,
    JWTStrategy,
)
from fastapi_users.authentication.strategy.base import Strategy
from fastapi_users.authentication.transport.base import Transport
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx_oauth.clients.github import GitHubOAuth2
from jupyverse_api.exceptions import RedirectException
from jupyverse_api.frontend import FrontendConfig
from starlette.requests import Request

from .config import _AuthConfig
from .db import User
from .models import UserCreate, UserRead


logger = logging.getLogger("auth")


@dataclass
class Res:
    cookie_authentication: Any
    current_user: Any
    update_user: Any
    fapi_users: Any
    get_user_manager: Any
    github_authentication: Any
    github_cookie_authentication: Any
    websocket_auth: Any


def get_backend(auth_config: _AuthConfig, frontend_config: FrontendConfig, db) -> Res:
    class NoAuthScheme:
        def __call__(self):
            return "noauth"

    class NoAuthTransport(Transport):
        scheme = NoAuthScheme()  # type: ignore

        async def get_login_response(self, token: str, response: Response):
            pass

        async def get_logout_response(self, response: Response):
            pass

        @staticmethod
        def get_openapi_login_responses_success():
            pass

        @staticmethod
        def get_openapi_logout_responses_success():
            pass

    class NoAuthStrategy(Strategy, Generic[models.UP, models.ID]):
        async def read_token(
            self, token: Optional[str], user_manager: BaseUserManager[models.UP, models.ID]
        ) -> Optional[models.UP]:
            active_user = await user_manager.user_db.get_by_email(auth_config.global_email)
            return active_user

        async def write_token(self, user: models.UP):
            pass

        async def destroy_token(self, token: str, user: models.UP):
            pass

    class GitHubTransport(CookieTransport):
        async def get_login_response(self, token: str, response: Response):
            await super().get_login_response(token, response)
            response.status_code = status.HTTP_302_FOUND
            response.headers["Location"] = "/lab"

    def get_noauth_strategy() -> NoAuthStrategy:
        return NoAuthStrategy()

    def get_jwt_strategy() -> JWTStrategy:
        return JWTStrategy(secret=db.secret, lifetime_seconds=None)

    noauth_authentication = AuthenticationBackend(
        name="noauth",
        transport=NoAuthTransport(),
        get_strategy=get_noauth_strategy,
    )

    cookie_authentication = AuthenticationBackend(
        name="cookie",
        transport=CookieTransport(cookie_secure=auth_config.cookie_secure),
        get_strategy=get_jwt_strategy,
    )

    github_cookie_authentication = AuthenticationBackend(
        name="github",
        transport=GitHubTransport(),
        get_strategy=get_jwt_strategy,
    )

    github_authentication = GitHubOAuth2(auth_config.client_id, auth_config.client_secret)

    class UserManager(UUIDIDMixin, BaseUserManager[User, uuid.UUID]):
        async def on_after_register(self, user: User, request: Optional[Request] = None):
            for oauth_account in user.oauth_accounts:
                if oauth_account.oauth_name == "github":
                    async with httpx.AsyncClient() as client:
                        r = (
                            await client.get(
                                f"https://api.github.com/user/{oauth_account.account_id}"
                            )
                        ).json()

                    await self.user_db.update(
                        user,
                        dict(
                            anonymous=False,
                            username=r["login"],
                            color=None,
                            avatar_url=r["avatar_url"],
                            is_active=True,
                        ),
                    )

    async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(db.get_user_db)):
        yield UserManager(user_db)

    def get_enabled_backends():
        if auth_config.mode == "noauth" and not frontend_config.collaborative:
            res = [noauth_authentication, github_cookie_authentication]
        else:
            res = [cookie_authentication, github_cookie_authentication]
        return res

    fapi_users = FastAPIUsers[User, uuid.UUID](
        get_user_manager,
        [
            noauth_authentication,
            cookie_authentication,
            github_cookie_authentication,
        ],
    )

    async def create_guest(user_manager):
        # workspace and settings are copied from global user
        # but this is a new user
        global_user = await user_manager.get_by_email(auth_config.global_email)
        user_id = str(uuid.uuid4())
        guest = dict(
            anonymous=True,
            email=f"{user_id}@jupyter.com",
            username=f"{user_id}@jupyter.com",
            password="",
            workspace=global_user.workspace,
            settings=global_user.settings,
            permissions={},
        )
        return await user_manager.create(UserCreate(**guest))

    def current_user(permissions: Optional[Dict[str, List[str]]] = None):
        async def _(
            response: Response,
            token: Optional[str] = None,
            user: Optional[User] = Depends(
                fapi_users.current_user(optional=True, get_enabled_backends=get_enabled_backends)
            ),
            user_manager: BaseUserManager[User, models.ID] = Depends(get_user_manager),
        ):
            if auth_config.mode == "user":
                # "user" authentication: check authorization
                if user and permissions:
                    for resource, actions in permissions.items():
                        user_actions_for_resource = user.permissions.get(resource, [])
                        if not all([a in user_actions_for_resource for a in actions]):
                            user = None
                            break
            else:
                # "noauth" or "token" authentication
                if frontend_config.collaborative:
                    if not user and auth_config.mode == "noauth":
                        user = await create_guest(user_manager)
                        await cookie_authentication.login(get_jwt_strategy(), user, response)

                    elif not user and auth_config.mode == "token":
                        global_user = await user_manager.get_by_email(auth_config.global_email)
                        if global_user and global_user.username == token:
                            user = await create_guest(user_manager)
                            await cookie_authentication.login(get_jwt_strategy(), user, response)
                else:
                    if auth_config.mode == "token":
                        global_user = await user_manager.get_by_email(auth_config.global_email)
                        if global_user and global_user.username == token:
                            user = global_user
                            await cookie_authentication.login(get_jwt_strategy(), user, response)

            if user:
                return user

            elif auth_config.login_url:
                raise RedirectException(auth_config.login_url)

            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        return _

    def websocket_auth(permissions: Optional[Dict[str, List[str]]] = None):
        """
        A function returning a dependency for the WebSocket connection.

        :param permissions: the permissions the user should be granted access to. The user should
        have access to at least one of them for the WebSocket to be opened.
        :returns: a dependency for the WebSocket connection. The dependency returns a tuple
        consisting of the websocket and the checked user permissions if the websocket is accepted,
        None otherwise.
        """

        async def _(
            websocket: WebSocket,
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(get_user_manager),
        ) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
            accept_websocket = False
            checked_permissions: Optional[Dict[str, List[str]]] = None
            if auth_config.mode == "noauth":
                accept_websocket = True
            elif "fastapiusersauth" in websocket._cookies:
                token = websocket._cookies["fastapiusersauth"]
                user = await get_jwt_strategy().read_token(token, user_manager)
                if user:
                    if auth_config.mode == "user":
                        # "user" authentication: check authorization
                        if permissions is None:
                            accept_websocket = True
                        else:
                            checked_permissions = {}
                            for resource, actions in permissions.items():
                                user_actions_for_resource = user.permissions.get(resource)
                                if user_actions_for_resource is None:
                                    continue
                                allowed = checked_permissions[resource] = []
                                for action in actions:
                                    if action in user_actions_for_resource:
                                        allowed.append(action)
                                        accept_websocket = True
                    else:
                        accept_websocket = True
            if accept_websocket:
                return websocket, checked_permissions
            else:
                await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
                return None

        return _

    async def update_user(
        user: UserRead = Depends(current_user()),
        user_db: SQLAlchemyUserDatabase = Depends(db.get_user_db),
    ):
        async def _(data: Dict[str, Any]) -> UserRead:
            await user_db.update(user, data)
            return user

        return _

    return Res(
        cookie_authentication=cookie_authentication,
        current_user=current_user,
        update_user=update_user,
        fapi_users=fapi_users,
        get_user_manager=get_user_manager,
        github_authentication=github_authentication,
        github_cookie_authentication=github_cookie_authentication,
        websocket_auth=websocket_auth,
    )
