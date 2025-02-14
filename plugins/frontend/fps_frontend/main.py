from fps import Module

from jupyverse_api.frontend import FrontendConfig


class FrontendModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.frontend_config = FrontendConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.frontend_config, FrontendConfig)
