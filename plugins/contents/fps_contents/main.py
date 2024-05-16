from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents

from .routes import _Contents


class ContentsComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]

        contents = _Contents(app, auth)
        add_resource(contents, types=Contents)
