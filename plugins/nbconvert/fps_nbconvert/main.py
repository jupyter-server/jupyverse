from fps import Module

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.nbconvert import Nbconvert

from .routes import _Nbconvert


class NbconvertModule(Module):
    async def prepare(self) -> None:
        app = await self.get(App)
        auth = await self.get(Auth)  # type: ignore[type-abstract]
        nbconvert = _Nbconvert(app, auth)
        self.put(nbconvert, Nbconvert)
