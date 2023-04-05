from __future__ import annotations

import webbrowser
from typing import Any, Callable, Dict, Sequence

from asgiref.typing import ASGI3Application
from asphalt.core import Component, Context
from asphalt.web.fastapi import FastAPIComponent
from fastapi import FastAPI
from pydantic import BaseModel

from ..app import App


class AppComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        app = await ctx.request_resource(FastAPI)

        _app = App(app)
        ctx.add_resource(_app)


class JupyverseComponent(FastAPIComponent):
    def __init__(
        self,
        components: dict[str, dict[str, Any] | None] | None = None,
        *,
        app: FastAPI | str | None = None,
        host: str = "127.0.0.1",
        port: int = 8000,
        open_browser: bool = False,
        query_params: Dict[str, Any] | None = None,
        debug: bool | None = None,
        middlewares: Sequence[Callable[..., ASGI3Application] | dict[str, Any]] = (),
    ) -> None:
        super().__init__(
            components,  # type: ignore
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

    async def start(
        self,
        ctx: Context,
    ) -> None:
        query_params = QueryParams(d={})
        host = self.host
        if not host.startswith("http"):
            host = f"http://{host}"
        host_url = Host(url=f"{host}:{self.port}/")
        ctx.add_resource(query_params)
        ctx.add_resource(host_url)

        await super().start(ctx)

        # at this point, the server has started
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
