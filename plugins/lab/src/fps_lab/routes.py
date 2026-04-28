import glob
import json
from collections.abc import Callable
from http import HTTPStatus
from importlib.metadata import entry_points
from pathlib import Path

import anyio
import json5  # type: ignore
from anyio import sleep
from anyio.abc import TaskGroup
from babel import Locale
from fastapi import Response, status
from fastapi.responses import FileResponse, RedirectResponse
from jupyverse_api import App
from jupyverse_auth import Auth, User
from jupyverse_frontend import FrontendConfig
from jupyverse_jupyterlab import JupyterLabConfig
from jupyverse_lab import Lab, PageConfig
from starlette.requests import Request


class _Lab(Lab):
    def __init__(
        self,
        app: App,
        auth: Auth,
        frontend_config: FrontendConfig,
        jupyterlab_config: JupyterLabConfig | None,
        page_config: PageConfig,
        exit_app: Callable[[], None],
        task_group: TaskGroup,
    ) -> None:
        super().__init__(app, auth, jupyterlab_config, page_config)

        self.frontend_config = frontend_config
        self.locale = "en"
        self._exit_app = exit_app
        self._task_group = task_group

    async def get_root(
        self,
        response: Response,
        redirect: str | None,
        user: User,
    ):
        # auto redirect
        response.status_code = status.HTTP_302_FOUND
        if redirect is None:
            redirect = self.frontend_config.base_url + self.redirect_after_root
        response.headers["Location"] = redirect

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
        for ep in entry_points(group="jupyterlab.languagepack"):
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

        for ep in entry_points(group="jupyterlab.languagepack"):
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
        extension_name: str,
        setting_name: str,
        user: User,
    ):
        overrides_path = anyio.Path(self.jlab_dir) / "settings" / "overrides.json"
        if await overrides_path.is_file():
            overrides = json.loads(await overrides_path.read_text())
        else:
            overrides = {}
        if "/" in extension_name:
            # scoped: e.g. @jupyterlab/notebook-extension
            org, name = extension_name.split("/", 1)
            if (
                org in ["@jupyterlab", "@notebook"]
                and await (
                    anyio.Path(self.jlab_dir) / "schemas" / org / name / f"{setting_name}.json"
                ).exists()
            ):
                schemas_parent = self.jlab_dir
                package = json.loads(
                    await (anyio.Path(self.jlab_dir) / "static" / "package.json").read_text()
                )
            else:
                schemas_parent = self.extensions_dir / org / name
                package = json.loads(
                    await (anyio.Path(schemas_parent) / "package.json").read_text()
                )
            schema = json.loads(
                await (
                    anyio.Path(schemas_parent) / "schemas" / org / name / f"{setting_name}.json"
                ).read_text()
            )
            key = f"{name}:{setting_name}"
        else:
            # flat: e.g. nbdime-jupyterlab
            ext_dir = anyio.Path(self.extensions_dir) / extension_name
            package = json.loads(await (ext_dir / "package.json").read_text())
            schema = json.loads(
                await (ext_dir / "schemas" / extension_name / f"{setting_name}.json").read_text()
            )
            key = f"{extension_name}:{setting_name}"
        id_ = f"{extension_name}:{setting_name}"
        setting = {
            "id": id_,
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
        settings_overrides = overrides.get(id_)
        if settings_overrides is not None:
            setting["settings"] = settings_overrides
            setting["raw"] = json.dumps(settings_overrides)
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

    async def shutdown(self, user: User):
        async def exit_app():
            await sleep(0.1)
            self._exit_app()

        self._task_group.start_soon(exit_app)

    async def get_settings(self, user: User):
        overrides_path = anyio.Path(self.jlab_dir) / "settings" / "overrides.json"
        if await overrides_path.is_file():
            overrides = json.loads(await overrides_path.read_text())
        else:
            overrides = {}
        if user:
            user_settings = json.loads(user.settings)
        else:
            user_settings = {}
        settings = []
        schemas = [self.jlab_dir / "schemas"]
        if self.labextensions_dir.is_dir():
            for d1 in self.labextensions_dir.iterdir():
                if (d1 / "schemas").exists():
                    schemas.append(d1 / "schemas")
                for d2 in d1.iterdir():
                    if (d2 / "schemas").exists():
                        schemas.append(d2 / "schemas")
        for s in schemas:
            for d1 in s.iterdir():
                for d2 in d1.iterdir():
                    if not d2.is_dir():
                        continue
                    package = json.loads((d2 / "package.json.orig").read_text())
                    for path in [p for p in d2.iterdir() if p.suffix == ".json"]:
                        schema = json.loads(path.read_text())
                        key = f"{path.parent.name}:{path.stem}"
                        id_ = f"{d1.name}/{key}"
                        setting = {
                            "id": id_,
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
                        settings_overrides = overrides.get(id_)
                        if settings_overrides is not None:
                            setting["settings"] = settings_overrides
                            setting["raw"] = json.dumps(settings_overrides)
                        settings.append(setting)
        return {"settings": settings}

    def get_federated_extensions(self, extensions_dir: Path) -> tuple[list, list]:
        federated_extensions = []
        disabled_extensions = []

        pattern = str(extensions_dir / "**" / "package.json")
        for path in glob.glob(pattern, recursive=True):
            package = json.loads(Path(path).read_text())
            if "jupyterlab" not in package:
                continue
            extension = package["jupyterlab"]["_build"]
            extension["name"] = package["name"]
            extension["description"] = package.get("description", "")
            federated_extensions.append(extension)

            for ext in package["jupyterlab"].get("disabledExtensions", []):
                disabled_extensions.append(ext)

        return federated_extensions, disabled_extensions
