import httpx
from fps import Module
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, AuthConfig

from .config import AuthJupyterHubConfig
from .db import Base
from .routes import auth_factory


class AuthJupyterHubModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.auth_jupyterhub_config = AuthJupyterHubConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.auth_jupyterhub_config, types=AuthConfig)
        app = await self.get(App)
        self.db_engine = create_async_engine(self.auth_jupyterhub_config.db_url)
        self.db_session = AsyncSession(self.db_engine)

        self.http_client = httpx.AsyncClient()
        auth_jupyterhub = auth_factory(app, self.db_session, self.http_client)
        self.put(auth_jupyterhub, types=Auth)

        async with self.db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def stop(self) -> None:
        await self.http_client.aclose()
        await self.db_session.close()
        await self.db_engine.dispose()
