import logging

from asphalt.core import Component, Context
from fastapi_users.exceptions import UserAlreadyExists
from jupyverse_api.auth import Auth, AuthConfig
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.app import App
from jupyverse_api.main import Host, QueryParams

from .config import _AuthConfig
from .routes import auth_factory


logger = logging.getLogger("auth")


class AuthComponent(Component):
    def __init__(self, **kwargs):
        self.auth_config = _AuthConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(self.auth_config, types=AuthConfig)

        app = await ctx.request_resource(App)
        frontend_config = await ctx.request_resource(FrontendConfig)

        auth = auth_factory(app, self.auth_config, frontend_config)
        ctx.add_resource(auth, types=Auth)

        await auth.db.create_db_and_tables()

        if self.auth_config.test:
            try:
                await auth.create_user(
                    username="admin@jupyter.com",
                    email="admin@jupyter.com",
                    password="jupyverse",
                    permissions={"admin": ["read", "write"]},
                )
            except UserAlreadyExists:
                pass

        try:
            await auth.create_user(
                username=self.auth_config.token,
                email=self.auth_config.global_email,
                password="",
                permissions={},
            )
        except UserAlreadyExists:
            global_user = await auth.get_user_by_email(self.auth_config.global_email)
            await auth._update_user(
                global_user,
                username=self.auth_config.token,
                permissions={},
            )

        if self.auth_config.mode == "token":
            query_params = await ctx.request_resource(QueryParams)
            host = await ctx.request_resource(Host)
            query_params.d["token"] = self.auth_config.token

            logger.info("")
            logger.info("To access the server, copy and paste this URL:")
            logger.info(f"{host.url}?token={self.auth_config.token}")
            logger.info("")
