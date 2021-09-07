import httpx  # type: ignore
from httpx_oauth.clients.github import GitHubOAuth2  # type: ignore
from fps.hooks import register_router  # type: ignore
from fps.config import Config  # type: ignore
from fastapi_users.authentication import CookieAuthentication  # type: ignore
from fastapi import APIRouter
from fastapi_users import FastAPIUsers  # type: ignore
from starlette.requests import Request
from fastapi import status
from sqlalchemy.orm import sessionmaker  # type: ignore

from .config import AuthConfig
from .models import (
    user_db,
    engine,
    UserTable,
    User,
    UserCreate,
    UserUpdate,
    UserDB,
    database,
    secret,
)


Session = sessionmaker(bind=engine)
session = Session()


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


auth_config = Config(AuthConfig)

cookie_authentication = LoginCookieAuthentication(
    cookie_secure=auth_config.cookie_secure, secret=secret
)

auth_backends = [cookie_authentication]

users = FastAPIUsers(
    user_db,
    auth_backends,
    User,
    UserCreate,
    UserUpdate,
    UserDB,
)

github_oauth_client = GitHubOAuth2(
    auth_config.client_id, auth_config.client_secret.get_secret_value()
)


async def on_after_register(user: UserDB, request):
    user.initialized = True
    await user_db.update(user)


async def on_after_github_register(user: UserDB, request: Request):
    r = httpx.get(
        f"https://api.github.com/user/{user.oauth_accounts[0].account_id}"
    ).json()
    user.initialized = True
    user.anonymous = False
    user.username = r["login"]
    user.name = r["name"]
    user.color = None
    user.avatar = r["avatar_url"]
    await user_db.update(user)


github_oauth_router = users.get_oauth_router(
    github_oauth_client, secret, after_register=on_after_github_register  # type: ignore
)
auth_router = users.get_auth_router(cookie_authentication)
user_register_router = users.get_register_router(on_after_register)  # type: ignore
users_router = users.get_users_router()

router = APIRouter()


@router.get("/auth/users")
async def get_users():
    users = session.query(UserTable).all()
    return [user for user in users if user.logged_in]


@router.on_event("startup")
async def startup():
    await database.connect()


@router.on_event("shutdown")
async def shutdown():
    await database.disconnect()


r_auth = register_router(auth_router)
r_register = register_router(user_register_router)
r_users = register_router(users_router, prefix="/auth/users")
r_github = register_router(github_oauth_router, prefix="/auth/github")
r = register_router(router)
