from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import AuthConfig
from jupyverse_api.login import Login

from .routes import _Login


class LoginComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth_config = await get_resource(AuthConfig, wait=True)

        login = _Login(app, auth_config)
        add_resource(login, types=Login)
