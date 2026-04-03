import logging

from fps import Module
from jupyverse_api import App
from jupyverse_contents import Contents

from .routes import git_factory

logger = logging.getLogger(__name__)


class JupyterLabGitModule(Module):
    dependencies = [Contents]

    async def prepare(self) -> None:
        app = await self.get(App)
        contents = await self.get(Contents)  # type: ignore[type-abstract]
        try:
            await contents.set_root_dir()
        except RuntimeError as e:
            logger.error("jupyterlab-git: cannot start, failed to get root directory: %s", e)
            raise
        git_router = git_factory(app, contents)
        self.put(git_router)
