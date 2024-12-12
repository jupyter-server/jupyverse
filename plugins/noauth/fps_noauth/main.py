from fastaio import Component

from jupyverse_api.auth import Auth

from .backends import _NoAuth


class NoAuthComponent(Component):
    async def prepare(self) -> None:
        no_auth = _NoAuth()
        self.add_resource(no_auth, types=Auth)
        self.done()
