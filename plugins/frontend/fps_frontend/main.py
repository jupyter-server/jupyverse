from fastaio import Component

from jupyverse_api.frontend import FrontendConfig


class FrontendComponent(Component):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.frontend_config = FrontendConfig(**kwargs)

    async def prepare(self) -> None:
        self.add_resource(self.frontend_config, types=FrontendConfig)
