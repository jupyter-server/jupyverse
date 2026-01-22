When Jupyverse is run using the `jupyverse` CLI, it internally launches a server. But it is also
possible to run Jupyverse through an external server. This allows to use any ASGI server you want,
and to use process replication if this server supports it.

## Exposing the FastAPI app

The following `main.py` will expose the FastAPI application in the `app` object, and use the ASGI
lifespan protocol to start and stop Jupyverse:

```py
from importlib.metadata import entry_points

from fastapi import FastAPI
from fps import get_root_module
from starlette.types import Receive, Scope, Send
from structlog import get_logger

log = get_logger()


class App:
    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            while True:
                message = await receive()
                if message["type"] == "lifespan.startup":
                    await self._start()
                    await send({"type": "lifespan.startup.complete"})
                elif message["type"] == "lifespan.shutdown":
                    await self._jupyverse_module.__aexit__(None, None, None)
                    await send({"type": "lifespan.shutdown.complete"})
                    return
        await self._app(scope, receive, send)

    async def _start(self) -> None:
        jupyverse_modules = {
            name: {"type": name}
            for name in [ep.name for ep in entry_points(group="jupyverse.modules")]
        }
        config = {
            "jupyverse": {
                "type": "jupyverse",
                "modules": jupyverse_modules,
                "config": {"start_server": False},
            }
        }
        self._jupyverse_module = await get_root_module(config).__aenter__()
        self._app = await self._jupyverse_module.get(FastAPI)
        auth_token = self._jupyverse_module.modules["auth"].config.token
        log.info(f"Auth token: {auth_token}")


app = App()
```

You can then use `uvicorn` to run the server, for instance:

```bash
uvicorn main:app
```
