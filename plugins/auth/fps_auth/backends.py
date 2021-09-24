from typing import Optional

from fps.exceptions import RedirectException  # type: ignore

import httpx
from httpx_oauth.clients.github import GitHubOAuth2  # type: ignore
from fastapi import Depends, Response, HTTPException, status

from fastapi_users.authentication import CookieAuthentication, JWTAuthentication  # type: ignore
from fastapi_users import FastAPIUsers, BaseUserManager  # type: ignore
from starlette.requests import Request

from .config import get_auth_config
from .db import secret, get_user_db
from .models import (
    User,
    UserDB,
    UserCreate,
    UserUpdate,
    UserDB
)

auth_config = get_auth_config()

class LoginCookieAuthentication(CookieAuthentication):
    async def get_login_response(self, user, response, user_manager):
        await super().get_login_response(user, response, user_manager)
        # auto redirect
        response.status_code = status.HTTP_302_FOUND
        response.headers["Location"] = "/lab"

cookie_authentication = LoginCookieAuthentication(secret=secret, name='cookie')
jwt_authentication = JWTAuthentication(secret=secret, lifetime_seconds=3600)
github_authentication = GitHubOAuth2(auth_config.client_id, auth_config.client_secret.get_secret_value())

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
                user.token = ""
                user.username = r["login"]
                user.name = r["name"]
                user.color = None
                user.avatar = r["avatar_url"]
        await self.user_db.update(user)

def get_user_manager(user_db=Depends(get_user_db)):
    yield UserManager(user_db)

fapi_users = FastAPIUsers(
    get_user_manager,
    [cookie_authentication, jwt_authentication],
    User,
    UserCreate,
    UserUpdate,
    UserDB
)

async def current_user(
    response: Response,
    token: Optional[str] = None,
    user: User = Depends(fapi_users.current_user(optional=True)),
    user_db = Depends(get_user_db),
    user_manager = Depends(get_user_manager)
):
    active_user = user

    if active_user :
        return active_user

    elif auth_config.mode == 'noauth' :
        active_user = await user_db.get_by_email(auth_config.guest_email)
    
    elif auth_config.mode == 'token' :
        tmp = await user_db.get_by_email(auth_config.guest_email)
        if tmp.token == token :
            active_user = tmp
            await cookie_authentication.get_login_response(tmp, response, user_manager)


    if active_user :
        return active_user

    elif auth_config.login_url :
        raise RedirectException(auth_config.login_url)

    else :
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED)
