from pathlib import Path
from typing import Optional, cast

from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from jupyverse_api.app import App
from jupyverse_api.auth import AuthConfig
from jupyverse_api.login import Login


class _AuthConfig(AuthConfig):
    login_url: Optional[str]


class _Login(Login):
    def __init__(
        self,
        app: App,
        auth_config: AuthConfig,
    ) -> None:
        super().__init__(app)

        router = APIRouter()
        prefix_static = Path(__file__).parent / "static"

        # fps_login needs an AuthConfig that has a login_url, such as fps_auth's config
        auth_config = cast(_AuthConfig, auth_config)
        auth_config.login_url = "/login"

        self.mount(
            "/static/login",
            StaticFiles(directory=prefix_static),
            name="static",
        )

        @router.get("/login")
        async def api_login():
            return FileResponse(prefix_static / "index.html")

        self.include_router(router)
