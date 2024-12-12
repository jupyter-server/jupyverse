from __future__ import annotations

from fastaio import Component

from anyio import create_task_group
from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs, YjsConfig

from .routes import _Yjs


class YjsComponent(Component):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.yjs_config = YjsConfig(**kwargs)

    async def prepare(self) -> None:
        self.add_resource(self.yjs_config, types=YjsConfig)

        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)
        self.contents = await self.get_resource(Contents)
        lifespan = await self.get_resource(Lifespan)

        self.yjs = _Yjs(app, auth, self.contents, lifespan)
        self.add_resource(self.yjs, types=Yjs)

        async with create_task_group() as tg:
            tg.start_soon(self.yjs.start)
            tg.start_soon(self.contents.file_id_manager.start)
            self.done()

    async def stop(self) -> None:
        await self.yjs.stop()
        await self.contents.file_id_manager.stop()
