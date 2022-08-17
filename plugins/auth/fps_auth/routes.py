from typing import Dict, List, Optional
from uuid import uuid4

from fastapi import APIRouter, Depends
from fastapi_users.password import PasswordHelper
from fps.config import get_config  # type: ignore
from fps.hooks import register_router  # type: ignore
from fps.logging import get_configured_logger  # type: ignore
from fps_uvicorn.config import UvicornConfig  # type: ignore
from sqlalchemy import select  # type: ignore

from .backends import (
    cookie_authentication,
    current_user,
    fapi_users,
    github_authentication,
    github_cookie_authentication,
)
from .config import get_auth_config
from .db import Session, User, UserDb, create_db_and_tables, secret
from .models import Permissions, UserCreate, UserRead, UserUpdate

logger = get_configured_logger("auth")

uvicorn_config = get_config(UvicornConfig)

router = APIRouter()


@router.on_event("startup")
async def startup():
    await create_db_and_tables()

    auth_config = get_auth_config()

    async with UserDb() as user_db:

        if auth_config.test:
            admin_user = await user_db.get_by_email("admin@jupyter.com")
            if not admin_user:
                admin_user = dict(
                    id=uuid4(),
                    anonymous=False,
                    email="admin@jupyter.com",
                    username="admin@jupyter.com",
                    hashed_password=PasswordHelper().hash("jupyverse"),
                    is_superuser=True,
                    is_active=True,
                    is_verified=True,
                    workspace="{}",
                    settings="{}",
                    permissions={"admin": ["read", "write"]},
                )
                await user_db.create(admin_user)

        global_user = await user_db.get_by_email(auth_config.global_email)
        if global_user:
            await user_db.update(global_user, {"hashed_password": auth_config.token})
        else:
            global_user = dict(
                id=uuid4(),
                anonymous=True,
                email=auth_config.global_email,
                username=auth_config.global_email,
                hashed_password=auth_config.token,
                is_superuser=False,
                is_active=False,
                is_verified=True,
                workspace="{}",
                settings="{}",
                permissions={},
            )
            await user_db.create(global_user)

    if auth_config.mode == "token":
        logger.info("")
        logger.info("To access the server, copy and paste this URL:")
        logger.info(
            f"http://{uvicorn_config.host}:{uvicorn_config.port}/?token={auth_config.token}"
        )
        logger.info("")


@router.get("/auth/users")
async def get_users(user: UserRead = Depends(current_user("admin"))):
    async with Session() as session:
        statement = select(User)
        users = (await session.execute(statement)).unique().all()
    return [usr.User for usr in users if usr.User.is_active]


@router.get("/api/me")
async def get_api_me(
    permissions_to_check: Optional[Permissions] = None,
    user: UserRead = Depends(current_user()),
):
    checked_permissions: Dict[str, List[str]] = {}
    if permissions_to_check is not None:
        permissions = permissions_to_check.permissions
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
async def get_me(user: UserRead = Depends(current_user("admin"))):
    return user


users_router.include_router(fapi_users.get_users_router(UserRead, UserUpdate))

# Cookie based auth login and logout
r_cookie_auth = register_router(fapi_users.get_auth_router(cookie_authentication), prefix="/auth")
r_register = register_router(
    fapi_users.get_register_router(UserRead, UserCreate),
    prefix="/auth",
    dependencies=[Depends(current_user("admin"))],
)
r_user = register_router(users_router, prefix="/auth/user")

# GitHub OAuth register router
r_github = register_router(
    fapi_users.get_oauth_router(github_authentication, github_cookie_authentication, secret),
    prefix="/auth/github",
)

r = register_router(router)
