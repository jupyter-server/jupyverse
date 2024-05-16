from asphalt.core import Component, add_resource

from jupyverse_api.frontend import FrontendConfig


class FrontendComponent(Component):
    def __init__(self, **kwargs):
        self.frontend_config = FrontendConfig(**kwargs)

    async def start(self) -> None:
        add_resource(self.frontend_config, types=FrontendConfig)
