from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import _AuthFiefConfig
from .routes import auth_factory


class AuthFiefModule(Module):
    def __init__(self, name: str, **kwargs):
        self.auth_fief_config = _AuthFiefConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.auth_fief_config, AuthConfig)

        app = await self.get(App)

        auth_fief = auth_factory(app, self.auth_fief_config)
        self.put(auth_fief, Auth)
