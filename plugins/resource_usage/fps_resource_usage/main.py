from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.resource_usage import ResourceUsage, ResourceUsageConfig

from .routes import _ResourceUsage


class ResourceUsageComponent(Component):
    def __init__(self, **kwargs):
        self.resource_usage_config = ResourceUsageConfig(**kwargs)

    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]

        resource_usage = _ResourceUsage(app, auth, self.resource_usage_config)
        add_resource(resource_usage, types=ResourceUsage)
