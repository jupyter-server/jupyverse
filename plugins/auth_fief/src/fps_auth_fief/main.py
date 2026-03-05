from fps import Module
from jupyverse_api import App
from jupyverse_auth import Auth, AuthConfig

from .config import _AuthFiefConfig
from .routes import auth_factory


class AuthFiefModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = _AuthFiefConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.config, AuthConfig)

        app = await self.get(App)

        auth_fief = auth_factory(app, self.config)
        self.put(auth_fief, Auth)
