import logging
import uuid
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
from starlette.requests import Request

from .db import Db, User
from .models import UserCreate, UserRead


logger = logging.getLogger("auth")


class Backend:
    def __init__(self, auth_config, frontend_config):
        self.auth_config = auth_config
        self.frontend_config = frontend_config
        self.db = db = Db(auth_config)

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

        def get_noauth_strategy() -> NoAuthStrategy:
            return NoAuthStrategy()

        self.noauth_authentication = AuthenticationBackend(
            name="noauth",
            transport=NoAuthTransport(),
            get_strategy=get_noauth_strategy,
        )
        self.cookie_authentication = AuthenticationBackend(
            name="cookie",
            transport=CookieTransport(cookie_secure=auth_config.cookie_secure),
            get_strategy=self._get_jwt_strategy,
        )
        self.github_cookie_authentication = AuthenticationBackend(
            name="github",
            transport=GitHubTransport(),
            get_strategy=self._get_jwt_strategy,
        )
        self.github_authentication = GitHubOAuth2(auth_config.client_id, auth_config.client_secret)

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

        self.UserManager = UserManager

        async def get_user_manager(user_db: SQLAlchemyUserDatabase = Depends(db.get_user_db)):
            yield UserManager(user_db)

        self.get_user_manager = get_user_manager

        self.fapi_users = FastAPIUsers[User, uuid.UUID](
            get_user_manager,
            [
                self.noauth_authentication,
                self.cookie_authentication,
                self.github_cookie_authentication,
            ],
        )

        async def update_user(
            user: UserRead = Depends(self.current_user()),
            user_db: SQLAlchemyUserDatabase = Depends(db.get_user_db),
        ):
            async def _(data: Dict[str, Any]) -> UserRead:
                await user_db.update(user, data)
                return user

            return _

        self.update_user = update_user

    def _get_jwt_strategy(self) -> JWTStrategy:
        return JWTStrategy(secret=self.db.secret, lifetime_seconds=None)

    def _get_enabled_backends(self):
        if self.auth_config.mode == "noauth" and not self.frontend_config.collaborative:
            res = [self.noauth_authentication, self.github_cookie_authentication]
        else:
            res = [self.cookie_authentication, self.github_cookie_authentication]
        return res

    async def _create_guest(self, user_manager):
        # workspace and settings are copied from global user
        # but this is a new user
        global_user = await user_manager.get_by_email(self.auth_config.global_email)
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

    def current_user(self, permissions: Optional[Dict[str, List[str]]] = None):
        async def _(
            response: Response,
            token: Optional[str] = None,
            user: Optional[User] = Depends(
                self.fapi_users.current_user(
                    optional=True, get_enabled_backends=self._get_enabled_backends
                )
            ),
            user_manager: BaseUserManager[User, models.ID] = Depends(self.get_user_manager),
        ):
            if self.auth_config.mode == "user":
                # "user" authentication: check authorization
                if user and permissions:
                    for resource, actions in permissions.items():
                        user_actions_for_resource = user.permissions.get(resource, [])
                        if not all([a in user_actions_for_resource for a in actions]):
                            user = None
                            break
            else:
                # "noauth" or "token" authentication
                if self.frontend_config.collaborative:
                    if not user and self.auth_config.mode == "noauth":
                        user = await self._create_guest(user_manager)
                        await self.cookie_authentication.login(
                            self._get_jwt_strategy(), user, response
                        )

                    elif not user and self.auth_config.mode == "token":
                        global_user = await user_manager.get_by_email(self.auth_config.global_email)
                        if global_user and global_user.username == token:
                            user = await self._create_guest(user_manager)
                            await self.cookie_authentication.login(
                                self._get_jwt_strategy(), user, response
                            )
                else:
                    if self.auth_config.mode == "token":
                        global_user = await user_manager.get_by_email(self.auth_config.global_email)
                        if global_user and global_user.username == token:
                            user = global_user
                            await self.cookie_authentication.login(
                                self._get_jwt_strategy(), user, response
                            )

            if user:
                return user

            elif self.auth_config.login_url:
                raise RedirectException(self.auth_config.login_url)

            else:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

        return _

    def websocket_auth(self, permissions: Optional[Dict[str, List[str]]] = None):
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
            user_manager: BaseUserManager[models.UP, models.ID] = Depends(self.get_user_manager),
        ) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
            accept_websocket = False
            checked_permissions: Optional[Dict[str, List[str]]] = None
            if self.auth_config.mode == "noauth":
                accept_websocket = True
            elif "fastapiusersauth" in websocket._cookies:
                token = websocket._cookies["fastapiusersauth"]
                user = await self._get_jwt_strategy().read_token(token, user_manager)
                if user:
                    if self.auth_config.mode == "user":
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

    @property
    def User(self):
        return UserRead


class NoAuthTransport(Transport):
    scheme = None  # type: ignore

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


class GitHubTransport(CookieTransport):
    async def get_login_response(self, token: str, response: Response):
        await super().get_login_response(token, response)
        response.status_code = status.HTTP_302_FOUND
        response.headers["Location"] = "/lab"
