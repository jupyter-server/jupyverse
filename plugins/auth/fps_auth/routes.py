from uuid import uuid4

from httpx_oauth.clients.github import GitHubOAuth2  # type: ignore
from fps.hooks import register_router  # type: ignore
from fps.config import get_config, FPSConfig  # type: ignore
from fastapi import APIRouter, Depends
from sqlalchemy.orm import sessionmaker  # type: ignore

from .config import get_auth_config
from .db import user_db, secret, database, engine, UserTable
from .backends import users, current_user, cookie_authentication, noauth_email
from .models import (
    User,
    UserDB,
)


Session = sessionmaker(bind=engine)
session = Session()

fps_config = get_config(FPSConfig)
auth_config = get_auth_config()


github_oauth_client = GitHubOAuth2(
    auth_config.client_id, auth_config.client_secret.get_secret_value()
)


github_oauth_router = users.get_oauth_router(
    github_oauth_client, secret  # type: ignore
)
auth_router = users.get_auth_router(cookie_authentication)
user_register_router = users.get_register_router()  # type: ignore
users_router = users.get_users_router()

router = APIRouter()

TOKEN_USER = None
USER_TOKEN = None


def set_user_token(user_token):
    global USER_TOKEN
    USER_TOKEN = user_token


def get_user_token():
    return USER_TOKEN


@router.on_event("startup")
async def startup():
    await database.connect()
    if auth_config.mode == "noauth":
        await create_noauth_user()
    elif auth_config.mode == "token":
        set_user_token(str(uuid4()))
        await create_token_user()


@router.on_event("shutdown")
async def shutdown():
    global TOKEN_USER
    await database.disconnect()
    if auth_config.mode == "token":
        await user_db.delete(TOKEN_USER)


async def create_noauth_user():
    user = await user_db.get_by_email(noauth_email)
    if user is None:
        user = UserDB(
            id="d4ded46b-a4df-4b51-8d83-ae19010272a7",
            email=noauth_email,
            hashed_password="",
        )
        await user_db.create(user)


async def create_token_user():
    global TOKEN_USER
    print("To access the server, copy and paste this URL:")
    print(f"{fps_config.host}:{fps_config.port}/?token={USER_TOKEN}")
    token_email = f"{USER_TOKEN}_user@jupyter.com"
    TOKEN_USER = UserDB(id=USER_TOKEN, email=token_email, hashed_password="")
    await user_db.create(TOKEN_USER)


@router.get("/auth/users")
async def get_users(user: User = Depends(current_user)):
    users = session.query(UserTable).all()
    return [user for user in users if user.logged_in]


r_auth = register_router(auth_router)
r_register = register_router(user_register_router)
r_users = register_router(users_router, prefix="/auth/users")
r_github = register_router(github_oauth_router, prefix="/auth/github")
r = register_router(router)
