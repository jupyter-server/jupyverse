from anyio import create_task_group
from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import AuthJupyterHubConfig
from .routes import auth_factory


class AuthJupyterHubModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = AuthJupyterHubConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.config, AuthConfig)
        app = await self.get(App)

        self.auth_jupyterhub = auth_factory(app, self.config)

        async with create_task_group() as self.tg:
            await self.tg.start(self.auth_jupyterhub.start)
            self.put(self.auth_jupyterhub, Auth, teardown_callback=self.auth_jupyterhub.stop)
            self.done()
