from uuid import uuid4
from fastapi_users.authentication import jwt

from fps.hooks import register_router  # type: ignore
from fps.config import get_config  # type: ignore
from fps.logging import get_configured_logger  # type: ignore
from fps_uvicorn.config import UvicornConfig  # type: ignore

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import sessionmaker  # type: ignore

from .config import get_auth_config
from .db import user_db, secret, database, engine, UserTable
from .backends import fapi_users, current_user, cookie_authentication, jwt_authentication, github_authentication
from .models import (
    User,
    UserDB
)

logger = get_configured_logger("auth")

Session = sessionmaker(bind=engine)
session = Session()

uvicorn_config = get_config(UvicornConfig)
auth_config = get_auth_config()

router = APIRouter()

@router.on_event("startup")
async def startup():
    await database.connect()
    guest = await user_db.get_by_email(auth_config.guest_email)

    if guest :
        guest.token = auth_config.token
        await user_db.update(guest)
        
    else :
        guest = UserDB(
            id=str(uuid4()),
            email=auth_config.guest_email,
            token=auth_config.token,
            hashed_password=""
        )
        await user_db.create(guest)
    
    logger.info("")
    logger.info("To access the server, copy and paste this URL:")
    logger.info(f"http://{uvicorn_config.host}:{uvicorn_config.port}/?token={auth_config.token}")
    logger.info("")


@router.on_event("shutdown")
async def shutdown():
    await database.disconnect()


@router.get("/auth/users")
async def get_users(user: User = Depends(current_user)):
    users = session.query(UserTable).all()
    return [user for user in users if user.logged_in]

@router.post("/auth/jwt/refresh")
async def refresh_jwt(response: Response, user=Depends(current_user)):
    return await jwt_authentication.get_login_response(user, response)

# Cookie based auth login, logout and register routes
r_cookie_auth = register_router(
    fapi_users.get_auth_router(cookie_authentication),
    prefix="/auth"
)
r_register = register_router(
    fapi_users.get_register_router(),
    prefix="/auth"
)
r_users = register_router(
    fapi_users.get_users_router(),
    prefix="/auth/users"
)

# JWT token based auth login, logout
r_jwt_auth = register_router(
    fapi_users.get_auth_router(jwt_authentication),
    prefix="/auth/jwt"
)

# GitHub OAuth register router
r_github = register_router(
  fapi_users.get_oauth_router(github_authentication, secret),
  prefix="/auth/github"
)

r = register_router(router)
