from __future__ import annotations

from asphalt.core import (
    Component,
    add_resource,
    get_resource,
    start_background_task_factory,
    start_service_task,
)

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.contents import Contents
from jupyverse_api.main import Lifespan
from jupyverse_api.yjs import Yjs

from .routes import _Yjs


class YjsComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]
        contents = await get_resource(Contents, wait=True)  # type: ignore[type-abstract]
        lifespan = await get_resource(Lifespan, wait=True)

        task_factory = await start_background_task_factory()
        yjs = _Yjs(app, auth, contents, lifespan, task_factory)
        add_resource(yjs, types=Yjs)

        await start_service_task(yjs.start, "Room manager", teardown_action=yjs.stop)
        await start_service_task(
            contents.file_id_manager.start,
            "File ID manager",
            teardown_action=contents.file_id_manager.stop,
        )
