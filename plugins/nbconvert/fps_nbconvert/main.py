from asphalt.core import Component, Context, add_resource, request_resource

from jupyverse_api.app import App
from jupyverse_api.auth import Auth
from jupyverse_api.nbconvert import Nbconvert

from .routes import _Nbconvert


class NbconvertComponent(Component):
    async def start(self) -> None:
        app = await request_resource(App)
        auth = await request_resource(Auth)  # type: ignore

        nbconvert = _Nbconvert(app, auth)
        await add_resource(nbconvert, types=Nbconvert)
