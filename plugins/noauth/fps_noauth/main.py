from asphalt.core import Component, Context
from jupyverse_api.auth import Auth

from .backends import _NoAuth


class NoAuthComponent(Component):
    async def start(
        self,
        ctx: Context,
    ) -> None:
        noauth = _NoAuth()
        ctx.add_resource(noauth, types=Auth)
