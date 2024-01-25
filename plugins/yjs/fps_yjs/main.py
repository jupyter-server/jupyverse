from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Optional

from asphalt.core import Component, Context, add_resource, request_resource, start_background_task

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.yjs import Yjs

from .routes import _Yjs


class YjsComponent(Component):
    async def start(self) -> AsyncGenerator[None, Optional[BaseException]]:
        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore
        contents = await request_resource(Contents)  # type: ignore

        yjs = _Yjs(app, auth, contents)
        await add_resource(yjs, types=Yjs)

        await start_background_task(yjs.room_manager.start, "Room manager", teardown_action=yjs.room_manager.stop)
        await start_background_task(contents.file_id_manager.start, "File ID manager", teardown_action=contents.file_id_manager.stop)
