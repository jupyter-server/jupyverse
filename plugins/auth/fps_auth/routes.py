import os
import json
from typing import Dict, Any

import httpx  # type: ignore
from httpx_oauth.clients.github import GitHubOAuth2  # type: ignore

from fastapi.responses import RedirectResponse

import fps  # type: ignore
from fastapi import APIRouter

# Create 'jupyterlab-auth/config.json' file with the following secrets:
# "client_id": ""
# "client_secret": ""
# "redirect_uri": ""

CLIENT_ID = ""
CLIENT_SECRET = ""
REDIRECT_URI = ""

USERS: Dict[str, Any] = {}
CURRENT_USER = None

config_file = os.path.join(os.path.dirname(__file__), "config.json")
if os.path.exists(config_file):
    with open(config_file) as f:
        conf = json.load(f)
        CLIENT_ID = conf["client_id"]
        CLIENT_SECRET = conf["client_secret"]
        REDIRECT_URI = conf["redirect_uri"]
        CLIENT = GitHubOAuth2(CLIENT_ID, CLIENT_SECRET)


def init(jupyverse):
    router.init(jupyverse)
    return router


router = APIRouter()


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
            REDIRECT_URI,
            scope=["read:user"],
        )
        return RedirectResponse(authorization_url)

    access_token = await CLIENT.get_access_token(code, REDIRECT_URI)
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
