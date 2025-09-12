from __future__ import annotations

from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.environments import Environments

from .environments import _Environments


class EnvironmentsModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        environments = _Environments(app, auth)
        self.put(environments, Environments)
