import contextlib
import json
import logging
from typing import Dict, List

from fastapi import FastAPI, APIRouter, Depends, Request
from jupyverse_api import Router
from jupyverse_api.auth import Auth
from jupyverse_api.frontend import FrontendConfig
from sqlalchemy import select

from .backends import Backend
from .config import _AuthConfig
from .db import User

from .models import UserCreate, UserRead, UserUpdate


logger = logging.getLogger("auth")


class _Auth(Backend, Auth, Router):
    def __init__(
        self,
        app: FastAPI,
        auth_config: _AuthConfig,
        frontend_config: FrontendConfig,
    ):
        Router.__init__(self, app)
        Backend.__init__(self, auth_config, frontend_config)

        self.auth_config = auth_config
        self.backend = backend = Backend(auth_config, frontend_config)

        db = self.db

        router = APIRouter()

        get_async_session_context = contextlib.asynccontextmanager(db.get_async_session)
        get_user_db_context = contextlib.asynccontextmanager(db.get_user_db)
        get_user_manager_context = contextlib.asynccontextmanager(backend.get_user_manager)

        @contextlib.asynccontextmanager
        async def _get_user_manager():
            async with get_async_session_context() as session:
                async with get_user_db_context(session) as user_db:
                    async with get_user_manager_context(user_db) as user_manager:
                        yield user_manager

        async def create_user(**kwargs):
            async with _get_user_manager() as user_manager:
                await user_manager.create(UserCreate(**kwargs))

        self.create_user = create_user

        async def _update_user(user, **kwargs):
            async with _get_user_manager() as user_manager:
                await user_manager.update(UserUpdate(**kwargs), user)

        self._update_user = _update_user

        async def get_user_by_email(user_email):
            async with _get_user_manager() as user_manager:
                return await user_manager.get_by_email(user_email)

        self.get_user_by_email = get_user_by_email

        @router.get("/auth/users")
        async def get_users(
            user: UserRead = Depends(self.current_user(permissions={"admin": ["read"]})),
        ):
            async with db.async_session_maker() as session:
                statement = select(User)
                users = (await session.execute(statement)).unique().all()
            return [usr.User for usr in users if usr.User.is_active]

        @router.get("/api/me")
        async def get_api_me(
            request: Request,
            user: UserRead = Depends(self.current_user()),
        ):
            checked_permissions: Dict[str, List[str]] = {}
            permissions = json.loads(
                dict(request.query_params).get("permissions", "{}").replace("'", '"')
            )
            if permissions:
                user_permissions = user.permissions
                for resource, actions in permissions.items():
                    user_resource_permissions = user_permissions.get(resource)
                    if user_resource_permissions is None:
                        continue
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

        # redefine GET /me because we want our current_user dependency
        # it is first defined in users_router and so it wins over the one in
        # fapi_users.get_users_router
        users_router = APIRouter()

        @users_router.get("/me")
        async def get_me(
            user: UserRead = Depends(self.current_user(permissions={"admin": ["read"]})),
        ):
            return user

        users_router.include_router(self.fapi_users.get_users_router(UserRead, UserUpdate))

        # Cookie based auth login and logout
        self.include_router(
            self.fapi_users.get_auth_router(self.cookie_authentication), prefix="/auth"
        )
        self.include_router(
            self.fapi_users.get_register_router(UserRead, UserCreate),
            prefix="/auth",
            dependencies=[Depends(self.current_user(permissions={"admin": ["write"]}))],
        )
        self.include_router(users_router, prefix="/auth/user")
        # GitHub OAuth register router
        self.include_router(
            self.fapi_users.get_oauth_router(
                self.github_authentication, self.github_cookie_authentication, db.secret
            ),
            prefix="/auth/github",
        )
        self.include_router(router)
