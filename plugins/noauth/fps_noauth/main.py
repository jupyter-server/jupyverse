from fps import Module

from jupyverse_api.auth import Auth

from .backends import _NoAuth


class NoAuthModule(Module):
    async def prepare(self) -> None:
        no_auth = _NoAuth()
        self.put(no_auth, Auth)
