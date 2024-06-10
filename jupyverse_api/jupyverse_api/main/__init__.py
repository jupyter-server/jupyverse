from __future__ import annotations

import webbrowser
from typing import Any, Callable, Dict, Sequence, Tuple

from anyio import Event
from asgiref.typing import ASGI3Application
from asphalt.core import Component, add_resource, get_resource, start_service_task
from asphalt.web.fastapi import FastAPIComponent
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from ..app import App


class AppComponent(Component):
    def __init__(
        self,
        *,
        mount_path: str | None = None,
    ) -> None:
        super().__init__()
        self.mount_path = mount_path

    async def start(self) -> None:
        app = await get_resource(FastAPI, wait=True)

        _app = App(app, mount_path=self.mount_path)
        add_resource(_app)


class JupyverseComponent(FastAPIComponent):
    def __init__(
        self,
        *,
        app: FastAPI | str | None = None,
        host: str = "127.0.0.1",
        port: int = 8000,
        allow_origin: Tuple[str, ...] = (),
        open_browser: bool = False,
        query_params: Dict[str, Any] | None = None,
        debug: bool | None = None,
        middlewares: Sequence[Callable[..., ASGI3Application] | dict[str, Any]] = (),
    ) -> None:
        if allow_origin:
            middleware = {
                "type": CORSMiddleware,
                "allow_origins": allow_origin,
                "allow_credentials": True,
                "allow_methods": ["*"],
                "allow_headers": ["*"],
            }
            middlewares = list(middlewares) + [middleware]
        super().__init__(
            app=app,
            host=host,
            port=port,
            debug=debug,
            middlewares=middlewares,
        )
        self.host = host
        self.port = port
        self.open_browser = open_browser
        self.query_params = query_params
        self.lifespan = Lifespan()

    async def prepare(self) -> None:
        query_params = QueryParams(d={})
        host = self.host
        if not host.startswith("http"):
            host = f"http://{host}"
        host_url = Host(url=f"{host}:{self.port}/")
        add_resource(query_params)
        add_resource(host_url)
        add_resource(self.lifespan)

        await super().prepare()

    async def start(self) -> None:
        await super().start()

        # at this point, the server has started
        await start_service_task(
            self.lifespan.shutdown_request.wait,
            "Server lifespan notifier",
            teardown_action=self.lifespan.shutdown_request.set,
        )

        if self.open_browser:
            qp = query_params.d
            if self.query_params:
                qp.update(**self.query_params)
            query_params_str = "?" + "&".join([f"{k}={v}" for k, v in qp.items()]) if qp else ""
            webbrowser.open_new_tab(f"{self.host}:{self.port}{query_params_str}")


class QueryParams(BaseModel):
    d: Dict[str, Any]


class Host(BaseModel):
    url: str


class Lifespan:
    def __init__(self):
        self.shutdown_request = Event()
