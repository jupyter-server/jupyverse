from fastapi import APIRouter, Depends
from jupyverse_api import Router
from jupyverse_api.auth import Auth, User
from jupyverse_api.app import App
from starlette.requests import Request

from .models import Backend, Install


class JupyterCAD(Router):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

        @router.post("/cad/backend-check")
        async def check_backend(
            request: Request, user: User = Depends(auth.current_user())
        ) -> Install:
            backend = Backend(**await request.json())
            if backend.backend == "FreeCAD":
                fc_installed = True
                try:
                    pass
                except ImportError:
                    fc_installed = False
                return Install(installed=fc_installed)
            elif backend == "JCAD":
                return Install(installed=True)
            else:
                return Install(installed=False)

        self.include_router(router)
