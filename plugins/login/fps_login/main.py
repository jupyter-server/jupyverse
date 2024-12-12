from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import AuthConfig
from jupyverse_api.login import Login

from .routes import _Login


class LoginComponent(Component):
    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth_config = await self.get_resource(AuthConfig)

        login = _Login(app, auth_config)
        self.add_resource(login, types=Login)

        self.done()
