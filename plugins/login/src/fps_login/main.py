from fps import Module
from jupyverse_api import App
from jupyverse_auth import AuthConfig
from jupyverse_login import Login

from .routes import _Login


class LoginModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth_config = await self.get(AuthConfig)

        login = _Login(app, auth_config)
        self.put(login, Login)
