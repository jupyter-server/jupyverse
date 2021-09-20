from uuid import uuid4
from typing import Optional

import httpx  # type: ignore
from httpx_oauth.clients.github import GitHubOAuth2  # type: ignore
from fps.hooks import register_router  # type: ignore
from fps.config import get_config, FPSConfig  # type: ignore
from fastapi_users.authentication import CookieAuthentication  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi_users import FastAPIUsers, BaseUserManager  # type: ignore
from starlette.requests import Request
from sqlalchemy.orm import sessionmaker  # type: ignore

from .config import get_auth_config
from .db import get_user_db, user_db, secret, database, engine, UserTable
from .models import (
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)


Session = sessionmaker(bind=engine)
session = Session()

fps_config = get_config(FPSConfig)
auth_config = get_auth_config()


class UserManager(BaseUserManager[UserCreate, UserDB]):
    user_db_model = UserDB

    async def on_after_register(self, user: UserDB, request: Optional[Request] = None):
        user.initialized = True
        for oauth_account in user.oauth_accounts:
            print(oauth_account)
            if oauth_account.oauth_name == "github":
                r = httpx.get(
                    f"https://api.github.com/user/{oauth_account.account_id}"
                ).json()
                user.anonymous = False
                user.username = r["login"]
                user.name = r["name"]
                user.color = None
                user.avatar = r["avatar_url"]
        await self.user_db.update(user)


def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


class LoginCookieAuthentication(CookieAuthentication):
    async def get_login_response(self, user, response):
        await super().get_login_response(user, response)
        # set user as logged in
        user.logged_in = True
        await user_db.update(user)
        # auto redirect
        response.status_code = status.HTTP_302_FOUND
        response.headers["Location"] = "/lab"

    async def get_logout_response(self, user, response):
        await super().get_logout_response(user, response)
        # set user as logged out
        user.logged_in = False
        await user_db.update(user)


cookie_authentication = LoginCookieAuthentication(
    cookie_secure=auth_config.cookie_secure, secret=secret
)

auth_backends = [cookie_authentication]

users = FastAPIUsers(
    get_user_manager,
    auth_backends,
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)

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
noauth_email = "noauth_user@jupyter.com"


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


def current_user(optional: bool = False):
    async def _(
        auth_config=Depends(get_auth_config),
        user: User = Depends(users.current_user(optional=True)),
    ):
        if auth_config.mode == "noauth":
            return await user_db.get_by_email(noauth_email)
        elif user is None and not optional:
            # FIXME: could be 403
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        else:
            return user

    return _


@router.get("/auth/users")
async def get_users(user: User = Depends(current_user())):
    users = session.query(UserTable).all()
    return [user for user in users if user.logged_in]


r_auth = register_router(auth_router)
r_register = register_router(user_register_router)
r_users = register_router(users_router, prefix="/auth/users")
r_github = register_router(github_oauth_router, prefix="/auth/github")
r = register_router(router)
