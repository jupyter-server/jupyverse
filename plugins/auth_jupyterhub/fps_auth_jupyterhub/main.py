import httpx
from asphalt.core import Component, ContainerComponent, Context, context_teardown
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import AuthJupyterHubConfig
from .db import Base
from .routes import auth_factory


class _AuthJupyterHubComponent(Component):
    @context_teardown
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(App)
        db_session = await ctx.request_resource(AsyncSession)
        db_engine = await ctx.request_resource(AsyncEngine)

        http_client = httpx.AsyncClient()
        auth_jupyterhub = auth_factory(app, db_session, http_client)
        ctx.add_resource(auth_jupyterhub, types=Auth)

        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        yield

        await http_client.aclose()


class AuthJupyterHubComponent(ContainerComponent):
    def __init__(self, **kwargs):
        self.auth_jupyterhub_config = AuthJupyterHubConfig(**kwargs)
        super().__init__()

    async def start(
        self,
        ctx: Context,
    ) -> None:
        ctx.add_resource(self.auth_jupyterhub_config, types=AuthConfig)
        self.add_component(
            "sqlalchemy",
            url=self.auth_jupyterhub_config.db_url,
        )
        self.add_component("auth_jupyterhub", type=_AuthJupyterHubComponent)
        await super().start(ctx)
