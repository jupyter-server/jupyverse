from asphalt.core import Component, Context
from jupyverse_api.frontend import FrontendConfig


class FrontendComponent(Component):
    def __init__(self, **kwargs):
        self.frontend_config = FrontendConfig(**kwargs)

    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(self.frontend_config, types=FrontendConfig)
