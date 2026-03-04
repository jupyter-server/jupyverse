from fps import Module
from jupyverse_api import App
from jupyverse_auth import Auth
from jupyverse_contents import Contents

from .routes import _Contents


class ContentsModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]

        contents = _Contents(app, auth)
        self.put(contents, Contents)
