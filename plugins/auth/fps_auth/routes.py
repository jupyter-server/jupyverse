from uuid import uuid4

from fps.hooks import register_router  # type: ignore
from fps.config import get_config  # type: ignore
from fps.logging import get_configured_logger  # type: ignore
from fps_uvicorn.config import UvicornConfig  # type: ignore

from fastapi import APIRouter, Depends
from sqlalchemy.orm import sessionmaker  # type: ignore

from .config import get_auth_config
from .db import user_db, secret, database, engine, UserTable
from .backends import (
    fapi_users,
    current_user,
    cookie_authentication,
    github_authentication,
)
from .models import User, UserDB, Role

logger = get_configured_logger("auth")

Session = sessionmaker(bind=engine)
session = Session()

uvicorn_config = get_config(UvicornConfig)

router = APIRouter()


@router.on_event("startup")
async def startup():
    auth_config = get_auth_config()

    await database.connect()
    global_user = await user_db.get_by_email(auth_config.global_email)

    if global_user:
        global_user.hashed_password = auth_config.token
        await user_db.update(global_user)

    else:
        global_user = UserDB(
            id=uuid4(),
            username="jovyan",
            email=auth_config.global_email,
            role=Role.ADMIN,
            anonymous=False,
            connected=False,
            name="jovyan",
            color=None,
            avatar_url=None,
            hashed_password=auth_config.token,
            is_superuser=True,
            is_active=True,
            is_verified=True
        )
        await user_db.create(global_user)

    if auth_config.mode == "token":
        logger.info("")
        logger.info("To access the server, copy and paste this URL:")
        logger.info(
            f"http://{uvicorn_config.host}:{uvicorn_config.port}/?token={auth_config.token}"
        )
        logger.info("")


@router.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@router.get("/auth/users")
async def get_users(user: User = Depends(current_user)):
    # TODO: create a db request that returns non critical info
    users = session.query(UserTable).all()
    resp = []
    for user in users:
        if user.connected and not user.is_superuser:
            resp.append({
                "id": user.id,
                "username": user.username,
                "anonymous": user.anonymous,
                "name": user.name,
                "color": user.color,
                "role": user.role,
                "email": user.email,
                "avatar_url": user.avatar_url
            })
    return resp


# Cookie based auth login and logout
r_cookie_auth = register_router(
    fapi_users.get_auth_router(cookie_authentication), prefix="/auth"
)
r_register = register_router(fapi_users.get_register_router(), prefix="/auth")
r_user = register_router(fapi_users.get_users_router(), prefix="/auth/user")

# GitHub OAuth register router
r_github = register_router(
    fapi_users.get_oauth_router(github_authentication, secret), prefix="/auth/github"
)

r = register_router(router)
