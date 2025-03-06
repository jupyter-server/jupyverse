from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.resource_usage import ResourceUsage, ResourceUsageConfig

from .routes import _ResourceUsage


class ResourceUsageModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = ResourceUsageConfig(**kwargs)

    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]

        resource_usage = _ResourceUsage(app, auth, self.config)
        self.put(resource_usage, ResourceUsage)
