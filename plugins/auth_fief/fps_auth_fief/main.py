from asphalt.core import Component, Context
from jupyverse_api.auth import Auth, AuthConfig
from jupyverse_api.app import App

from .config import _AuthFiefConfig
from .routes import auth_factory


class AuthFiefComponent(Component):
    def __init__(self, **kwargs):
        self.auth_fief_config = _AuthFiefConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(self.auth_fief_config, types=AuthConfig)

        app = await ctx.request_resource(App)

        auth_fief = auth_factory(app, self.auth_fief_config)
        ctx.add_resource(auth_fief, types=Auth)
