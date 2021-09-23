from typing import Optional

import httpx
from fastapi import Depends, HTTPException, status
from fastapi_users.authentication import BaseAuthentication, CookieAuthentication  # type: ignore
from fastapi_users import FastAPIUsers, BaseUserManager  # type: ignore
from starlette.requests import Request
from fps.exceptions import RedirectException  # type: ignore

from .models import (
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)
from .config import get_auth_config
from .db import secret, get_user_db


NOAUTH_EMAIL = "noauth_user@jupyter.com"
NOAUTH_USER = UserDB(
    id="d4ded46b-a4df-4b51-8d83-ae19010272a7",
    email=NOAUTH_EMAIL,
    hashed_password="",
)


class NoAuthAuthentication(BaseAuthentication):
    def __init__(self, user: UserDB, name: str = "noauth"):
        super().__init__(name, logout=False)
        self.user = user
        self.scheme = None  # type: ignore

    async def __call__(self, credentials, user_manager):
        noauth_user = await user_manager.user_db.get_by_email(NOAUTH_EMAIL)
        return noauth_user or self.user


noauth_authentication = NoAuthAuthentication(NOAUTH_USER)


class UserManager(BaseUserManager[UserCreate, UserDB]):
    user_db_model = UserDB

    async def on_after_register(self, user: UserDB, request: Optional[Request] = None):
        user.initialized = True
        for oauth_account in user.oauth_accounts:
            if oauth_account.oauth_name == "github":
                async with httpx.AsyncClient() as client:
                    r = (
                        await client.get(
                            f"https://api.github.com/user/{oauth_account.account_id}"
                        )
                    ).json()
                user.anonymous = False
                user.username = r["login"]
                user.name = r["name"]
                user.color = None
                user.avatar = r["avatar_url"]
        await self.user_db.update(user)


class LoginCookieAuthentication(CookieAuthentication):
    async def get_login_response(self, user, response, user_manager):
        await super().get_login_response(user, response, user_manager)
        # set user as logged in
        user.logged_in = True
        await user_manager.user_db.update(user)
        # auto redirect
        response.status_code = status.HTTP_302_FOUND
        response.headers["Location"] = "/lab"

    async def get_logout_response(self, user, response, user_manager):
        await super().get_logout_response(user, response, user_manager)
        # set user as logged out
        user.logged_in = False
        await user_manager.user_db.update(user)


cookie_authentication = LoginCookieAuthentication(
    cookie_secure=get_auth_config().cookie_secure, secret=secret
)


def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


users = FastAPIUsers(
    get_user_manager,
    [noauth_authentication, cookie_authentication],
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)


async def get_enabled_backends(auth_config=Depends(get_auth_config)):
    if auth_config.mode == "noauth":
        return [noauth_authentication]
    return [cookie_authentication]


def current_user():
    async def _(
        user: User = Depends(
            users.current_user(optional=True, get_enabled_backends=get_enabled_backends)
        ),
        auth_config=Depends(get_auth_config),
    ):
        if user is None:
            if auth_config.login_url:
                raise RedirectException(auth_config.login_url)
            else:
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
        else:
            return user

    return _
