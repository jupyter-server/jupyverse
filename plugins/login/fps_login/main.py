from asphalt.core import Component, Context, add_resource, request_resource

from jupyverse_api.app import App
from jupyverse_api.auth import AuthConfig
from jupyverse_api.login import Login

from .routes import _Login


class LoginComponent(Component):
    async def start(self) -> None:
        app = await request_resource(App)
        auth_config = await request_resource(AuthConfig)

        login = _Login(app, auth_config)
        await add_resource(login, types=Login)
