import sys
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional, Tuple

from fastapi import APIRouter, Depends, Request, Response
from fastapi.staticfiles import StaticFiles
from jupyverse_api import Router
from jupyverse_api.jupyterlab import JupyterLabConfig

from ..auth import Auth, User
from ..app import App


class Lab(Router, ABC):
    prefix_dir: Path
    jlab_dir: Path
    labextensions_dir: Path
    extensions_dir: Path
    redirect_after_root: str

    def __init__(self, app: App, auth: Auth, jupyterlab_config: Optional[JupyterLabConfig]):
        super().__init__(app)

        self.prefix_dir = Path(sys.prefix)
        self.extensions_dir = self.prefix_dir / "share" / "jupyter" / "labextensions"
        self.federated_extensions, disabled_extensions = self.get_federated_extensions(
            self.extensions_dir
        )
        if jupyterlab_config is not None:
            import jupyterlab as jupyterlab_module  # type: ignore

            jlab_dev_mode = jupyterlab_config.dev_mode
        else:
            jlab_dev_mode = False
        if jlab_dev_mode:
            self.jlab_dir = Path(jupyterlab_module.__file__).parents[1] / "dev_mode"
        else:
            self.jlab_dir = self.prefix_dir / "share" / "jupyter" / "lab"
        self.labextensions_dir = self.prefix_dir / "share" / "jupyter" / "labextensions"
        for ext in self.federated_extensions:
            name = ext["name"]
            self.mount(
                f"/lab/extensions/{name}/static",
                StaticFiles(directory=self.extensions_dir / name / "static"),
                name=name,
            )

        self.mount(
            "/lab/api/themes",
            StaticFiles(directory=self.jlab_dir / "themes"),
            name="themes",
        )

        router = APIRouter()

        @router.get("/", name="root")
        async def get_root(
            response: Response,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_root(response, user)

        @router.get("/favicon.ico")
        async def get_favicon():
            return await self.get_favicon()

        @router.get("/static/notebook/components/MathJax/{rest_of_path:path}")
        async def get_mathjax(rest_of_path):
            return await self.get_mathjax(rest_of_path)

        @router.get("/lab/api/listings/@jupyterlab/extensionmanager-extension/listings.json")
        async def get_listings(user: User = Depends(auth.current_user())):
            return await self.get_listings(user)

        @router.get("/lab/api/extensions")
        async def get_extensions(user: User = Depends(auth.current_user())):
            return await self.get_extensions(user)

        @router.get("/lab/api/translations/")
        async def get_translations_(
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_translations_(user)

        @router.get("/lab/api/translations")
        async def get_translations(user: User = Depends(auth.current_user())):
            return await self.get_translations(user)

        @router.get("/lab/api/translations/{language}")
        async def get_translation(
            language,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_translation(language, user)

        @router.get("/lab/api/settings/{name0}/{name1}:{name2}")
        async def get_setting(
            name0,
            name1,
            name2,
            user: User = Depends(auth.current_user()),
        ):
            return await self.get_setting(name0, name1, name2, user)

        @router.put(
            "/lab/api/settings/@jupyterlab/{name0}:{name1}",
            status_code=204,
        )
        async def change_setting(
            request: Request,
            name0,
            name1,
            user: User = Depends(auth.current_user()),
            user_update=Depends(auth.update_user),
        ):
            return await self.change_setting(request, name0, name1, user, user_update)

        @router.get("/lab/api/settings")
        async def get_settings(user: User = Depends(auth.current_user())):
            return await self.get_settings(user)

        self.include_router(router)

    @abstractmethod
    def get_federated_extensions(self, extensions_dir: Path) -> Tuple[List, List]:
        ...

    @abstractmethod
    async def get_root(
        self,
        response: Response,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_favicon(self):
        ...

    @abstractmethod
    async def get_mathjax(self, rest_of_path):
        ...

    @abstractmethod
    async def get_listings(self, user: User):
        ...

    @abstractmethod
    async def get_extensions(self, user: User):
        ...

    @abstractmethod
    async def get_translations_(
        self,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_translations(self, user: User):
        ...

    @abstractmethod
    async def get_translation(
        self,
        language,
        user: User,
    ):
        ...

    @abstractmethod
    async def get_setting(
        self,
        name0,
        name1,
        name2,
        user: User,
    ):
        ...

    @abstractmethod
    async def change_setting(
        self,
        request: Request,
        name0,
        name1,
        user: User,
        user_update,
    ):
        ...

    @abstractmethod
    async def get_settings(self, user: User):
        ...
