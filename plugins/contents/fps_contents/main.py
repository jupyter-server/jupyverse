from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents

from .routes import _Contents


class ContentsComponent(Component):
    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)  # type: ignore

        contents = _Contents(app, auth)
        self.add_resource(contents, types=Contents)
