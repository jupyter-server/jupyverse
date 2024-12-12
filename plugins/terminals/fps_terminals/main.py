import sys
from typing import Type

from anyio import create_task_group
from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.terminals import Terminals, TerminalServer

from .routes import _Terminals

_TerminalServer: Type[TerminalServer]
if sys.platform == "win32":
    from .win_server import _TerminalServer
else:
    from .server import _TerminalServer


class TerminalsComponent(Component):
    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)

        self.terminals = _Terminals(app, auth, _TerminalServer)
        self.add_resource(self.terminals, types=Terminals)
        async with create_task_group() as tg:
            tg.start_soon(self.terminals.start)
            self.done()

    async def stop(self) -> None:
        await self.terminals.stop()
