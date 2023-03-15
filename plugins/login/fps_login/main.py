from asphalt.core import Component, Context
from jupyverse_api.auth import AuthConfig
from jupyverse_api.login import Login
from jupyverse_api.app import App

from .routes import _Login


class LoginComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth_config = await ctx.request_resource(AuthConfig)

        login = _Login(app, auth_config)
        ctx.add_resource(login, types=Login)
