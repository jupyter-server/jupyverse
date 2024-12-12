from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.resource_usage import ResourceUsage, ResourceUsageConfig

from .routes import _ResourceUsage


class ResourceUsageComponent(Component):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.resource_usage_config = ResourceUsageConfig(**kwargs)

    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)

        resource_usage = _ResourceUsage(app, auth, self.resource_usage_config)
        self.add_resource(resource_usage, types=ResourceUsage)
