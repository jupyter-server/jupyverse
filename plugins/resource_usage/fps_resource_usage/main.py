from asphalt.core import Component, add_resource, request_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.resource_usage import ResourceUsage, ResourceUsageConfig

from .routes import _ResourceUsage


class ResourceUsageComponent(Component):
    def __init__(self, **kwargs):
        self.resource_usage_config = ResourceUsageConfig(**kwargs)

    async def start(self) -> None:
        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore

        resource_usage = _ResourceUsage(app, auth, self.resource_usage_config)
        await add_resource(resource_usage, types=ResourceUsage)
