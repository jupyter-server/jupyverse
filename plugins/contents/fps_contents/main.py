from asphalt.core import Component, Context
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents, ContentsConfig

from .routes import _Contents


class ContentsComponent(Component):
    def __init__(self, **kwargs) -> None:
        self.contents_config = ContentsConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        auth = await ctx.request_resource(Auth)  # type: ignore

        contents = _Contents(app, auth, self.contents_config)
        ctx.add_resource(contents, types=Contents)
