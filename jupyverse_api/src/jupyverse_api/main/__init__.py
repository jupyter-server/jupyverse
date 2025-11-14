from __future__ import annotations

import logging
import webbrowser

import structlog
from anyio import Event, create_task_group
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fps import Module
from fps.web.fastapi import FastAPIModule
from pydantic import BaseModel, Json

from jupyverse_api import Config

from ..app import App

logger = structlog.get_logger()


class AppModule(Module):
    def __init__(
        self,
        name: str,
        *,
        mount_path: str | None = None,
    ) -> None:
        super().__init__(name)
        self.mount_path = mount_path

    async def prepare(self) -> None:
        app = await self.get(FastAPI)
        _app = App(app, mount_path=self.mount_path)
        self.put(_app)


class JupyverseModule(FastAPIModule):
    def __init__(self, name: str, **kwargs) -> None:
        self.jupyverse_config = JupyverseConfig(**kwargs)
        if self.jupyverse_config.debug:
            structlog.stdlib.recreate_defaults(log_level=logging.DEBUG)
        super().__init__(
            name,
            debug=self.jupyverse_config.debug,
        )
        self.lifespan = Lifespan()
        if self.jupyverse_config.start_server:
            self.add_module(
                "fps.web.server:ServerModule",
                "server",
                host=self.jupyverse_config.host,
                port=self.jupyverse_config.port,
            )

    async def prepare(self) -> None:
        await super().prepare()
        app = await self.get(App)
        if self.jupyverse_config.allow_origins:
            app.add_middleware(
                CORSMiddleware,
                allow_origins=self.jupyverse_config.allow_origins,
                allow_credentials=True,
                allow_methods=["*"],
                allow_headers=["*"],
            )
        self._query_params = QueryParams(d={})
        self._host = self.jupyverse_config.host
        if not self._host.startswith("http"):
            self._host = f"http://{self._host}"
        self._port = self.jupyverse_config.port
        host_url = Host(url=f"{self._host}:{self._port}/")
        self.put(self._query_params)
        self.put(host_url)
        self.put(self.lifespan)

    async def start(self) -> None:
        async with create_task_group() as tg:
            tg.start_soon(super().start)
            if self.jupyverse_config.start_server:
                await self.modules["server"].started.wait()

            # at this point, the server has started
            qp = self._query_params.d
            if self.jupyverse_config.query_params:
                qp.update(**self.jupyverse_config.query_params)
            query_params_str = "?" + "&".join([f"{k}={v}" for k, v in qp.items()]) if qp else ""
            url = f"{self._host}:{self._port}{query_params_str}"
            logger.info("Server running", url=url)
            if self.jupyverse_config.open_browser:
                webbrowser.open_new_tab(url)

    async def stop(self) -> None:
        self.lifespan.shutdown_request.set()


class QueryParams(BaseModel):
    d: dict[str, str]


class Host(BaseModel):
    url: str


class Lifespan:
    def __init__(self):
        self.shutdown_request = Event()


class JupyverseConfig(Config):
    start_server: bool = True
    host: str = "127.0.0.1"
    port: int = 8000
    allow_origins: Json[list[str]] = []
    open_browser: bool = False
    query_params: Json[dict[str, str]] = {}
    debug: bool = False
