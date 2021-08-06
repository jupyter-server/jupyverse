from typing import Any, Dict

import fps  # type: ignore
import httpx  # type: ignore
from fastapi import APIRouter
from fastapi.responses import RedirectResponse
from fps.config import Config
from httpx_oauth.clients.github import GitHubOAuth2  # type: ignore

from .config import AuthConfig

router = APIRouter()
config = Config(AuthConfig)

CLIENT = GitHubOAuth2(config.client_id, config.client_secret)
USERS: Dict[str, Any] = {}
CURRENT_USER = None


@router.get("/auth/users")
async def get_users():
    return USERS.values()


@router.get("/auth/user")
async def get_user():
    return CURRENT_USER


@router.get("/login")
async def login(code: str = ""):
    if not code:
        authorization_url = await CLIENT.get_authorization_url(
            config.redirect_uri,
            scope=["read:user"],
        )
        return RedirectResponse(authorization_url)

    access_token = await CLIENT.get_access_token(code, config.redirect_uri)
    async with httpx.AsyncClient() as client:
        r = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": "token " + access_token["access_token"]},
        )
    github_user = r.json()
    user = {
        "initialized": True,
        "anonymous": False,
        "id": github_user["id"],
        "name": github_user["name"],
        "username": github_user["login"],
        "color": None,
        "email": github_user["email"],
        "avatar": github_user["avatar_url"],
    }
    global CURRENT_USER
    CURRENT_USER = user
    # TODO: set cookie
    return RedirectResponse("/")


r = fps.hooks.register_router(router)
