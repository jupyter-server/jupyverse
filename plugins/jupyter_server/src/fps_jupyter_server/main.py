from fps import Module
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.main import Lifespan

from .jupyter_server import JupyterServer


class JupyterServerModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)
        lifespan = await self.get(Lifespan)

        async with JupyterServer(app, auth, lifespan.shutdown_request) as jupyter_server:
            self.put(jupyter_server)
            self.done()
