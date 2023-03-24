import json
import logging
import os
import sys
from glob import glob
from http import HTTPStatus
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import json5  # type: ignore
import pkg_resources
from babel import Locale
from fastapi import APIRouter, Depends, Response, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request

import jupyverse
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLabConfig
from jupyverse_api.lab import Lab


logger = logging.getLogger("lab")


class _Lab(Lab):
    def __init__(
        self,
        app: App,
        auth: Auth,
        frontend_config: FrontendConfig,
        jupyterlab_config: Optional[JupyterLabConfig],
    ) -> None:
        super().__init__(app)

        self.auth = auth
        self.frontend_config = frontend_config

        if jupyterlab_config is not None:
            import jupyterlab as jupyterlab_module  # type: ignore

            jlab_dev_mode = jupyterlab_config.dev_mode
        else:
            jlab_dev_mode = False

        self.locale = "en"

        self.prefix_dir = Path(sys.prefix)
        if jlab_dev_mode:
            self.jlab_dir = Path(jupyterlab_module.__file__).parents[1] / "dev_mode"
        else:
            self.jlab_dir = self.prefix_dir / "share" / "jupyter" / "lab"

    def init_router(
        self, router: APIRouter, redirect_after_root: str
    ) -> Tuple[Path, List[Dict[str, Any]]]:
        extensions_dir = self.prefix_dir / "share" / "jupyter" / "labextensions"
        federated_extensions, disabled_extensions = self.get_federated_extensions(extensions_dir)

        for ext in federated_extensions:
            name = ext["name"]
            self.mount(
                f"/lab/extensions/{name}/static",
                StaticFiles(directory=extensions_dir / name / "static"),
                name=name,
            )

        self.mount(
            "/lab/api/themes",
            StaticFiles(directory=self.jlab_dir / "themes"),
            name="themes",
        )

        @router.get("/", name="root")
        async def get_root(
            response: Response,
            user: User = Depends(self.auth.current_user()),
        ):
            # auto redirect
            response.status_code = status.HTTP_302_FOUND
            response.headers["Location"] = self.frontend_config.base_url + redirect_after_root

        @router.get("/favicon.ico")
        async def get_favicon():
            return FileResponse(Path(jupyverse.__file__).parent / "static" / "favicon.ico")

        @router.get("/static/notebook/components/MathJax/{rest_of_path:path}")
        async def get_mathjax(rest_of_path):
            return RedirectResponse(
                "https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/" + rest_of_path
            )

        @router.get("/lab/api/listings/@jupyterlab/extensionmanager-extension/listings.json")
        async def get_listings(user: User = Depends(self.auth.current_user())):
            return {
                "blocked_extensions_uris": [],
                "allowed_extensions_uris": [],
                "blocked_extensions": [],
                "allowed_extensions": [],
            }

        @router.get("/lab/api/extensions")
        async def get_extensions(user: User = Depends(self.auth.current_user())):
            return federated_extensions

        @router.get("/lab/api/translations/")
        async def get_translations_(
            user: User = Depends(self.auth.current_user()),
        ):
            return RedirectResponse(f"{self.frontend_config.base_url}lab/api/translations")

        @router.get("/lab/api/translations")
        async def get_translations(user: User = Depends(self.auth.current_user())):
            locale = Locale.parse("en")
            display_name = (locale.get_display_name(self.locale) or "").capitalize()
            native_name = (locale.get_display_name() or "").capitalize()
            data = {
                "en": {
                    "displayName": display_name,
                    "nativeName": native_name,
                }
            }
            for ep in pkg_resources.iter_entry_points(group="jupyterlab.languagepack"):
                locale = Locale.parse(ep.name)
                data[ep.name] = {
                    "displayName": display_name,
                    "nativeName": native_name,
                }
            return {"data": data, "message": ""}

        @router.get("/lab/api/translations/{language}")
        async def get_translation(
            language,
            user: User = Depends(self.auth.current_user()),
        ):
            if language == "en":
                self.locale = language
                return {}
            for ep in pkg_resources.iter_entry_points(group="jupyterlab.languagepack"):
                if ep.name == language:
                    break
            else:
                return {"data": {}, "message": f"Language pack '{language}' not installed!"}
            self.locale = language
            package = ep.load()
            data = {}
            for path in (Path(package.__file__).parent / "locale" / language / "LC_MESSAGES").glob(
                "*.json"
            ):
                with open(path) as f:
                    data.update({path.stem: json.load(f)})
            return {"data": data, "message": ""}

        @router.get("/lab/api/settings/{name0}/{name1}:{name2}")
        async def get_setting(
            name0,
            name1,
            name2,
            user: User = Depends(self.auth.current_user()),
        ):
            with open(self.jlab_dir / "static" / "package.json") as f:
                package = json.load(f)
            if name0 in ["@jupyterlab", "@retrolab"]:
                schemas_parent = self.jlab_dir
            else:
                schemas_parent = extensions_dir / name0 / name1
            with open(schemas_parent / "schemas" / name0 / name1 / f"{name2}.json") as f:
                schema = json.load(f)
            key = f"{name1}:{name2}"
            setting = {
                "id": f"@jupyterlab/{key}",
                "schema": schema,
                "version": package["version"],
                "raw": "{}",
                "settings": {},
                "last_modified": None,
                "created": None,
            }
            if user:
                user_settings = json.loads(user.settings)
                if key in user_settings:
                    setting.update(user_settings[key])
                    setting["settings"] = json5.loads(user_settings[key]["raw"])
            return setting

        @router.put(
            "/lab/api/settings/@jupyterlab/{name0}:{name1}",
            status_code=204,
        )
        async def change_setting(
            request: Request,
            name0,
            name1,
            user: User = Depends(self.auth.current_user()),
            user_update=Depends(self.auth.update_user),
        ):
            settings = json.loads(user.settings)
            settings[f"{name0}:{name1}"] = await request.json()
            await user_update({"settings": json.dumps(settings)})
            return Response(status_code=HTTPStatus.NO_CONTENT.value)

        @router.get("/lab/api/settings")
        async def get_settings(user: User = Depends(self.auth.current_user())):
            with open(self.jlab_dir / "static" / "package.json") as f:
                package = json.load(f)
            if user:
                user_settings = json.loads(user.settings)
            else:
                user_settings = {}
            settings = []
            for path in (self.jlab_dir / "schemas" / "@jupyterlab").glob("*/*.json"):
                with open(path) as f:
                    schema = json.load(f)
                key = f"{path.parent.name}:{path.stem}"
                setting = {
                    "id": f"@jupyterlab/{key}",
                    "schema": schema,
                    "version": package["version"],
                    "raw": "{}",
                    "settings": {},
                    "warning": None,
                    "last_modified": None,
                    "created": None,
                }
                if key in user_settings:
                    setting.update(user_settings[key])
                    setting["settings"] = json5.loads(user_settings[key]["raw"])
                settings.append(setting)
            return {"settings": settings}

        return self.prefix_dir, federated_extensions

    def get_federated_extensions(self, extensions_dir: Path) -> Tuple[List, List]:
        federated_extensions = []
        disabled_extensions = []

        for path in glob(os.path.join(extensions_dir, "**", "package.json"), recursive=True):
            with open(path) as f:
                package = json.load(f)
            if "jupyterlab" not in package:
                continue
            extension = package["jupyterlab"]["_build"]
            extension["name"] = package["name"]
            extension["description"] = package["description"]
            federated_extensions.append(extension)

            for ext in package["jupyterlab"].get("disabledExtensions", []):
                disabled_extensions.append(ext)

        return federated_extensions, disabled_extensions
