from typing import Optional

import httpx
from fastapi import Depends, status
from fastapi.security.base import SecurityBase
from fastapi_users.authentication import BaseAuthentication, CookieAuthentication  # type: ignore
from fastapi_users import FastAPIUsers, BaseUserManager  # type: ignore
from starlette.requests import Request

from .models import (
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)
from .config import get_auth_config
from .db import secret, get_user_db


class NoAuthAuthentication(BaseAuthentication):
    def __init__(self, user: UserDB, name: str = "noauth"):
        super().__init__(name, logout=False)
        self.user = user
        self.scheme = SecurityBase

    async def __call__(self, credentials, user_manager):
        # always return the user no matter what
        return self.user


noauth_email = "noauth_user@jupyter.com"
no_auth_user = UserDB(email=noauth_email, hashed_password="")
no_auth_authentication = NoAuthAuthentication(no_auth_user)
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
    cookie_secure=auth_config.cookie_secure, secret=secret
)


def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)


if auth_config.mode == "noauth":
    auth_backend = no_auth_authentication
else:
    auth_backend = cookie_authentication

users = FastAPIUsers(
    get_user_manager,
    [auth_backend],
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)


async def get_enabled_backends(auth_config=Depends(get_auth_config)):
    if auth_config.mode == "noauth":
        return [no_auth_authentication]
    return [cookie_authentication]


current_user = users.current_user(get_enabled_backends=get_enabled_backends)
