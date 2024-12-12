from fastaio import Component

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.nbconvert import Nbconvert

from .routes import _Nbconvert


class NbconvertComponent(Component):
    async def prepare(self) -> None:
        app = await self.get_resource(App)
        auth = await self.get_resource(Auth)
        nbconvert = _Nbconvert(app, auth)
        self.add_resource(nbconvert, types=Nbconvert)
        self.done()
