from __future__ import annotations

from anyio import create_task_group
from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.file_id import FileId
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs, YjsConfig

from .routes import _Yjs


class YjsModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = YjsConfig(**kwargs)

    async def prepare(self) -> None:
        self.put(self.config, YjsConfig)

        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        contents = await self.get(Contents)  # type: ignore[type-abstract]
        file_id = await self.get(FileId)  # type: ignore[type-abstract]
        lifespan = await self.get(Lifespan)

        self.yjs = _Yjs(app, auth, contents, file_id, lifespan)

        async with create_task_group() as tg:
            await tg.start(self.yjs.start)
            self.put(self.yjs, Yjs, teardown_callback=self.yjs.stop)
            self.done()
