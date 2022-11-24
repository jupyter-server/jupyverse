import contextlib
import json
from typing import Dict, List

from fastapi import APIRouter, Depends, Request
from fastapi_users.exceptions import UserAlreadyExists
from fps.config import get_config  # type: ignore
from fps.hooks import register_router  # type: ignore
from fps.logging import get_configured_logger  # type: ignore
from fps_uvicorn.cli import add_query_params  # type: ignore
from fps_uvicorn.config import UvicornConfig  # type: ignore
from sqlalchemy import select  # type: ignore

from .backends import (
    cookie_authentication,
    current_user,
    fapi_users,
    get_user_manager,
    github_authentication,
    github_cookie_authentication,
)
from .config import get_auth_config
from .db import (
    User,
    async_session_maker,
    create_db_and_tables,
    get_async_session,
    get_user_db,
    secret,
)
from .models import UserCreate, UserRead, UserUpdate

logger = get_configured_logger("auth")

auth_config = get_auth_config()
if auth_config.mode == "token":
    add_query_params({"token": auth_config.token})

router = APIRouter()


get_async_session_context = contextlib.asynccontextmanager(get_async_session)
get_user_db_context = contextlib.asynccontextmanager(get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(get_user_manager)


@contextlib.asynccontextmanager
async def _get_user_manager():
    async with get_async_session_context() as session:
        async with get_user_db_context(session) as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                yield user_manager


async def create_user(**kwargs):
    async with _get_user_manager() as user_manager:
        await user_manager.create(UserCreate(**kwargs))


async def update_user(user, **kwargs):
    async with _get_user_manager() as user_manager:
        await user_manager.update(UserUpdate(**kwargs), user)


async def get_user_by_email(user_email):
    async with _get_user_manager() as user_manager:
        return await user_manager.get_by_email(user_email)


@router.on_event("startup")
async def startup():
    await create_db_and_tables()

    if auth_config.test:
        try:
            await create_user(
                username="admin@jupyter.com",
                email="admin@jupyter.com",
                password="jupyverse",
                permissions={"admin": ["read", "write"]},
            )
        except UserAlreadyExists:
            pass

    try:
        await create_user(
            username=auth_config.token,
            email=auth_config.global_email,
            password="",
            permissions={},
        )
    except UserAlreadyExists:
        global_user = await get_user_by_email(auth_config.global_email)
        await update_user(
            global_user,
            username=auth_config.token,
            permissions={},
        )

    if auth_config.mode == "token":
        uvicorn_config = get_config(UvicornConfig)
        logger.info("")
        logger.info("To access the server, copy and paste this URL:")
        logger.info(
            f"http://{uvicorn_config.host}:{uvicorn_config.port}/?token={auth_config.token}"
        )
        logger.info("")


@router.get("/auth/users")
async def get_users(user: UserRead = Depends(current_user(permissions={"admin": ["read"]}))):
    async with async_session_maker() as session:
        statement = select(User)
        users = (await session.execute(statement)).unique().all()
    return [usr.User for usr in users if usr.User.is_active]


@router.get("/api/me")
async def get_api_me(
    request: Request,
    user: UserRead = Depends(current_user()),
):
    checked_permissions: Dict[str, List[str]] = {}
    permissions = json.loads(dict(request.query_params).get("permissions", "{}").replace("'", '"'))
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
# it is first defined in users_router and so it wins over the one in fapi_users.get_users_router
users_router = APIRouter()


@users_router.get("/me")
async def get_me(user: UserRead = Depends(current_user(permissions={"admin": ["read"]}))):
    return user


users_router.include_router(fapi_users.get_users_router(UserRead, UserUpdate))

# Cookie based auth login and logout
r_cookie_auth = register_router(fapi_users.get_auth_router(cookie_authentication), prefix="/auth")
r_register = register_router(
    fapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    dependencies=[Depends(current_user(permissions={"admin": ["write"]}))],
)
r_user = register_router(users_router, prefix="/auth/user")

# GitHub OAuth register router
r_github = register_router(
    fapi_users.get_oauth_router(github_authentication, github_cookie_authentication, secret),
    prefix="/auth/github",
)

r = register_router(router)
