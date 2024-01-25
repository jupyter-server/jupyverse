from asphalt.core import Component, add_resource

from jupyverse_api.auth import Auth

from .backends import _NoAuth


class NoAuthComponent(Component):
    async def start(self) -> None:
        no_auth = _NoAuth()
        add_resource(no_auth, types=Auth)
