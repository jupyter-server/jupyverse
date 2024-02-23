from asphalt.core import Component, add_resource, request_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents

from .routes import _Contents


class ContentsComponent(Component):
    async def start(self) -> None:
        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore

        contents = _Contents(app, auth)
        await add_resource(contents, types=Contents)
