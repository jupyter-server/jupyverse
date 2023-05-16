import json
import logging
import os
from glob import glob
from http import HTTPStatus
from pathlib import Path
from typing import List, Optional, Tuple

import json5  # type: ignore
import pkg_resources
from babel import Locale
from fastapi import Response, status
from fastapi.responses import FileResponse, RedirectResponse
from starlette.requests import Request

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
        jupyterlab_config: Optional[JupyterLabConfig] = None,
    ) -> None:
        super().__init__(app, auth, jupyterlab_config)

        self.frontend_config = frontend_config
        self.locale = "en"

    async def get_root(
        self,
        response: Response,
        user: User,
    ):
        # auto redirect
        response.status_code = status.HTTP_302_FOUND
        response.headers["Location"] = self.frontend_config.base_url + self.redirect_after_root

    async def get_favicon(self):
        return FileResponse(Path(__file__).parent / "static" / "favicon.ico")

    async def get_mathjax(self, rest_of_path):
        return RedirectResponse(
            "https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/" + rest_of_path
        )

    async def get_listings(self, user: User):
        return {
            "blocked_extensions_uris": [],
            "allowed_extensions_uris": [],
            "blocked_extensions": [],
            "allowed_extensions": [],
        }

    async def get_extensions(self, user: User):
        return self.federated_extensions

    async def get_translations_(
        self,
        user: User,
    ):
        return RedirectResponse(f"{self.frontend_config.base_url}lab/api/translations")

    async def get_translations(self, user: User):
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

    async def get_translation(
        self,
        language,
        user: User,
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

    async def get_setting(
        self,
        name0,
        name1,
        name2,
        user: User,
    ):
        with open(self.jlab_dir / "static" / "package.json") as f:
            package = json.load(f)
        if name0 in ["@jupyterlab", "@retrolab"]:
            schemas_parent = self.jlab_dir
        else:
            schemas_parent = self.extensions_dir / name0 / name1
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

    async def change_setting(
        self,
        request: Request,
        name0,
        name1,
        user: User,
        user_update,
    ):
        settings = json.loads(user.settings)
        settings[f"{name0}:{name1}"] = await request.json()
        await user_update({"settings": json.dumps(settings)})
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def get_settings(self, user: User):
        if user:
            user_settings = json.loads(user.settings)
        else:
            user_settings = {}
        settings = []
        schemas = [self.jlab_dir / "schemas"]
        for d1 in self.labextensions_dir.iterdir():
            if (d1 / "schemas").exists():
                schemas.append(d1 / "schemas")
            for d2 in d1.iterdir():
                if (d2 / "schemas").exists():
                    schemas.append(d2 / "schemas")
        for s in schemas:
            for d1 in s.iterdir():
                for d2 in d1.iterdir():
                    package = json.loads((d2 / "package.json.orig").read_text())
                    for path in [p for p in d2.iterdir() if p.suffix == ".json"]:
                        schema = json.loads(path.read_text())
                        key = f"{path.parent.name}:{path.stem}"
                        setting = {
                            "id": f"{d1.name}/{key}",
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
