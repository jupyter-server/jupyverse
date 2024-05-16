from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import _AuthFiefConfig
from .routes import auth_factory


class AuthFiefComponent(Component):
    def __init__(self, **kwargs):
        self.auth_fief_config = _AuthFiefConfig(**kwargs)

    async def start(self) -> None:
        add_resource(self.auth_fief_config, types=AuthConfig)

        app = await get_resource(App, wait=True)

        auth_fief = auth_factory(app, self.auth_fief_config)
        add_resource(auth_fief, types=Auth)
