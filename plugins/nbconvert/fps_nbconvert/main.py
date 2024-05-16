from asphalt.core import Component, add_resource, get_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.nbconvert import Nbconvert

from .routes import _Nbconvert


class NbconvertComponent(Component):
    async def start(self) -> None:
        app = await get_resource(App, wait=True)
        auth = await get_resource(Auth, wait=True)  # type: ignore[type-abstract]

        nbconvert = _Nbconvert(app, auth)
        add_resource(nbconvert, types=Nbconvert)
