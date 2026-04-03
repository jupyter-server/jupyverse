from fps import Module
from jupyverse_api import App
from jupyverse_contents import Contents

from .routes import GitRouter


class JupyterLabGitModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        contents = await self.get(Contents)  # type: ignore[type-abstract]
        git_router = GitRouter(app, contents)
        self.put(git_router)
