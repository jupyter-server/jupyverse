import json
from pathlib import Path
import sys
from glob import glob
from http import HTTPStatus
import pkg_resources  # type: ignore
from typing import Optional

from babel import Locale  # type: ignore
import jupyverse  # type: ignore
from fastapi import Response, Depends, status
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request  # type: ignore

from fps_auth.db import get_user_db  # type: ignore
from fps_auth.backends import (  # type: ignore
    current_user,
    cookie_authentication,
    LoginCookieAuthentication,
    get_user_manager,
)
from fps_auth.models import User  # type: ignore
from fps_auth.config import get_auth_config  # type: ignore

from .config import get_lab_config  # type: ignore


def init_router(router, redirect_after_root):
    prefix_dir: Path = Path(sys.prefix)
    LOCALE = "en"

    federated_extensions = []

    for path in glob(
        str(prefix_dir / "share" / "jupyter" / "labextensions" / "**" / "package.json"),
        recursive=True,
    ):
        with open(path) as f:
            package = json.load(f)
        name = package["name"]
        extension = package["jupyterlab"]["_build"]
        extension["name"] = name
        federated_extensions.append(extension)
        router.mount(
            f"/lab/extensions/{name}/static",
            StaticFiles(
                directory=prefix_dir
                / "share"
                / "jupyter"
                / "labextensions"
                / name
                / "static"
            ),
            name=name,
        )

    router.mount(
        "/lab/api/themes",
        StaticFiles(directory=prefix_dir / "share" / "jupyter" / "lab" / "themes"),
        name="themes",
    )

    @router.get("/")
    async def get_root(
        response: Response,
        token: Optional[str] = None,
        auth_config=Depends(get_auth_config),
        lab_config=Depends(get_lab_config),
        user_db=Depends(get_user_db),
        user_manager=Depends(get_user_manager),
    ):
        if token and auth_config.mode == "token":
            user = await user_db.get(token)
            if user:
                await super(
                    LoginCookieAuthentication, cookie_authentication
                ).get_login_response(user, response, user_manager)
        # auto redirect
        response.status_code = status.HTTP_302_FOUND
        response.headers["Location"] = lab_config.base_url + redirect_after_root

    @router.get("/favicon.ico")
    async def get_favicon():
        return FileResponse(Path(jupyverse.__file__).parent / "static" / "favicon.ico")

    @router.get("/static/notebook/components/MathJax/{rest_of_path:path}")
    async def get_mathjax(rest_of_path):
        return RedirectResponse(
            "https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/" + rest_of_path
        )

    @router.get(
        "/lab/api/listings/@jupyterlab/extensionmanager-extension/listings.json"
    )
    async def get_listings():
        return {
            "blocked_extensions_uris": [],
            "allowed_extensions_uris": [],
            "blocked_extensions": [],
            "allowed_extensions": [],
        }

    @router.get("/lab/api/translations")
    async def get_translations():
        locale = Locale.parse("en")
        data = {
            "en": {
                "displayName": locale.get_display_name(LOCALE).capitalize(),
                "nativeName": locale.get_display_name().capitalize(),
            }
        }
        for ep in pkg_resources.iter_entry_points(group="jupyterlab.languagepack"):
            locale = Locale.parse(ep.name)
            data[ep.name] = {
                "displayName": locale.get_display_name(LOCALE).capitalize(),
                "nativeName": locale.get_display_name().capitalize(),
            }
        return {"data": data, "message": ""}

    @router.get("/lab/api/translations/{language}")
    async def get_translation(
        language,
    ):
        global LOCALE
        if language == "en":
            LOCALE = language
            return {}
        for ep in pkg_resources.iter_entry_points(group="jupyterlab.languagepack"):
            if ep.name == language:
                break
        else:
            return {"data": {}, "message": f"Language pack '{language}' not installed!"}
        LOCALE = language
        package = ep.load()
        data = {}
        for path in (
            Path(package.__file__).parent / "locale" / "fr_FR" / "LC_MESSAGES"
        ).glob("*.json"):
            with open(path) as f:
                data.update({path.stem: json.load(f)})
        return {"data": data, "message": ""}

    @router.get("/lab/api/settings/{name0}/{name1}:{name2}")
    async def get_setting(
        name0,
        name1,
        name2,
        user: User = Depends(current_user()),
    ):
        with open(
            prefix_dir / "share" / "jupyter" / "lab" / "static" / "package.json"
        ) as f:
            package = json.load(f)
        if name0 == "@jupyterlab":
            lab_or_extensions = Path("lab")
        else:
            lab_or_extensions = Path("labextensions") / name0 / name1
        with open(
            prefix_dir
            / "share"
            / "jupyter"
            / lab_or_extensions
            / "schemas"
            / name0
            / name1
            / f"{name2}.json"
        ) as f:
            schema = json.load(f)
        key = f"{name1}:{name2}"
        result = {
            "id": f"@jupyterlab/{key}",
            "schema": schema,
            "version": package["version"],
            "raw": "{}",
            "settings": {},
            "last_modified": None,
            "created": None,
        }
        if user:
            settings = json.loads(user.settings)
            if key in settings:
                result.update(settings[key])
        return result

    @router.put(
        "/lab/api/settings/@jupyterlab/{name0}:{name1}",
        status_code=204,
    )
    async def change_setting(
        request: Request,
        name0,
        name1,
        user: User = Depends(current_user()),
        user_db=Depends(get_user_db),
    ):
        settings = json.loads(user.settings)
        settings[f"{name0}:{name1}"] = await request.json()
        user.settings = json.dumps(settings)
        await user_db.update(user)
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    @router.get("/lab/api/settings")
    async def get_settings(user: User = Depends(current_user())):
        with open(
            prefix_dir / "share" / "jupyter" / "lab" / "static" / "package.json"
        ) as f:
            package = json.load(f)
        if user:
            user_settings = json.loads(user.settings)
        else:
            user_settings = {}
        settings = []
        for path in (
            prefix_dir / "share" / "jupyter" / "lab" / "schemas" / "@jupyterlab"
        ).glob("*/*.json"):
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
            settings.append(setting)
        return {"settings": settings}

    return prefix_dir, federated_extensions
