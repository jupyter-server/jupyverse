from __future__ import annotations

from anyio import Event, create_task_group
from fps import Module

from jupyverse_api.environments import Environments

from .micromamba import Micromamba


class EnvironmentMicromambaModule(Module):
    async def prepare(self) -> None:
        self.stop_event = Event()
        environments = await self.get(Environments)  # type: ignore[type-abstract]
        async with create_task_group() as tg:
            environments.add_package_manager("micromamba", Micromamba(tg))
            self.done()
            await self.stop_event.wait()

    async def stop(self) -> None:
        self.stop_event.set()
