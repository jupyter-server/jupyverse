from asphalt.core import (
    Component,
    ContainerComponent,
    add_resource,
    get_resource,
    start_service_task,
)
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import AuthJupyterHubConfig
from .db import Base
from .routes import auth_factory


class _AuthJupyterHubComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        db_session = await get_resource(AsyncSession, wait=True)
        db_engine = await get_resource(AsyncEngine, wait=True)

        auth_jupyterhub = auth_factory(app, db_session)
        await start_service_task(auth_jupyterhub.start, "JupyterHub Auth", auth_jupyterhub.stop)
        add_resource(auth_jupyterhub, types=Auth)

        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)


class AuthJupyterHubComponent(ContainerComponent):
    def __init__(self, **kwargs):
        self.auth_jupyterhub_config = AuthJupyterHubConfig(**kwargs)
        super().__init__()

    async def start(self) -> None:
        add_resource(self.auth_jupyterhub_config, types=AuthConfig)
        self.add_component(
            "sqlalchemy",
            url=self.auth_jupyterhub_config.db_url,
        )
        self.add_component("auth_jupyterhub", type=_AuthJupyterHubComponent)
        await super().start()
