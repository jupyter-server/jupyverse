import json
from pathlib import Path
import sys
from glob import glob
from http import HTTPStatus
import pkg_resources  # type: ignore
from typing import Optional

from babel import Locale  # type: ignore
from pydantic import UUID4
from starlette.requests import Request  # type: ignore
from fps.hooks import register_router  # type: ignore
import retrolab  # type: ignore
from fastapi import APIRouter, Response, Depends, status
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from fps_auth.db import get_user_db  # type: ignore
from fps_auth.backends import (  # type: ignore
    current_user,
    cookie_authentication,
    LoginCookieAuthentication,
    get_user_manager,
)
from fps_auth.models import User  # type: ignore
from fps_auth.config import get_auth_config  # type: ignore

from .config import get_rlab_config

LOCALE = "en"
router = APIRouter()
retrolab_dir = Path(retrolab.__file__).parent
prefix_dir = Path(sys.prefix)

router.mount(
    "/static/retro",
    StaticFiles(directory=retrolab_dir / "static"),
    name="static",
)

router.mount(
    "/lab/extensions/@retrolab/lab-extension/static",
    StaticFiles(directory=retrolab_dir / "labextension" / "static"),
    name="labextension/static",
)

router.mount(
    "/lab/api/themes",
    StaticFiles(directory=prefix_dir / "share" / "jupyter" / "lab" / "themes"),
    name="themes",
)

for path1 in (retrolab_dir / "labextension" / "static").glob("remoteEntry.*.js"):
    load = f"static/{path1.name}"
    break
federated_extensions = [
    {
        "extension": "./extension",
        "load": load,
        "name": "@retrolab/lab-extension",
        "style": "./style",
    }
]
for path2 in glob(
    str(prefix_dir / "share" / "jupyter" / "labextensions" / "**" / "package.json"),
    recursive=True,
):
    with open(path2) as f:
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


@router.get("/")
async def get_root(
    response: Response,
    token: Optional[UUID4] = None,
    auth_config=Depends(get_auth_config),
    rlab_config=Depends(get_rlab_config),
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
    response.headers["Location"] = rlab_config.base_url + "retro/tree"


@router.get("/retro/tree", response_class=HTMLResponse)
async def get_tree(rlab_config=Depends(get_rlab_config)):
    return get_index("Tree", "tree", rlab_config.collaborative, rlab_config.base_url)


@router.get("/retro/notebooks/{name}", response_class=HTMLResponse)
async def get_notebook(
    name: str,
    user: User = Depends(current_user()),
    rlab_config=Depends(get_rlab_config),
):
    return get_index(name, "notebooks", rlab_config.collaborative, rlab_config.base_url)


@router.get("/retro/consoles/{name}", response_class=HTMLResponse)
async def get_console(
    name: str,
    user: User = Depends(current_user()),
    rlab_config=Depends(get_rlab_config),
):
    return get_index(name, "consoles", rlab_config.collaborative, rlab_config.base_url)


@router.get("/retro/terminals/{name}", response_class=HTMLResponse)
async def get_terminal(
    name: str,
    user: User = Depends(current_user()),
    rlab_config=Depends(get_rlab_config),
):
    return get_index(name, "terminals", rlab_config.collaborative, rlab_config.base_url)


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


def get_index(doc_name, retro_page, collaborative, base_url="/"):
    page_config = {
        "appName": "RetroLab",
        "appNamespace": "retro",
        "appSettingsDir": str(prefix_dir / "share" / "jupyter" / "lab" / "settings"),
        "appUrl": "/lab",
        "appVersion": retrolab.__version__,
        "baseUrl": base_url,
        "cacheFiles": True,
        "collaborative": collaborative,
        "disabledExtensions": [],
        "extraLabextensionsPath": [],
        "federated_extensions": federated_extensions,
        "frontendUrl": "/retro/",
        "fullAppUrl": f"{base_url}lab",
        "fullLabextensionsUrl": f"{base_url}lab/extensions",
        "fullLicensesUrl": f"{base_url}lab/api/licenses",
        "fullListingsUrl": f"{base_url}lab/api/listings",
        "fullMathjaxUrl": f"{base_url}static/notebook/components/MathJax/MathJax.js",
        "fullSettingsUrl": f"{base_url}lab/api/settings",
        "fullStaticUrl": f"{base_url}static/retro",
        "fullThemesUrl": f"{base_url}lab/api/themes",
        "fullTranslationsApiUrl": f"{base_url}lab/api/translations",
        "fullTreeUrl": f"{base_url}lab/tree",
        "fullWorkspacesApiUrl": f"{base_url}lab/api/workspaces",
        "labextensionsPath": [str(prefix_dir / "share" / "jupyter" / "labextensions")],
        "labextensionsUrl": "/lab/extensions",
        "licensesUrl": "/lab/api/licenses",
        "listingsUrl": "/lab/api/listings",
        "mathjaxConfig": "TeX-AMS-MML_HTMLorMML-full,Safe",
        "retroLogo": False,
        "retroPage": retro_page,
        "schemasDir": str(prefix_dir / "share" / "jupyter" / "lab" / "schemas"),
        "settingsUrl": "/lab/api/settings",
        "staticDir": str(retrolab_dir / "static"),
        "templatesDir": str(retrolab_dir / "templates"),
        "terminalsAvailable": True,
        "themesDir": str(prefix_dir / "share" / "jupyter" / "lab" / "themes"),
        "themesUrl": "/lab/api/themes",
        "translationsApiUrl": "/lab/api/translations",
        "treeUrl": "/lab/tree",
        "workspacesApiUrl": "/lab/api/workspaces",
        "wsUrl": "",
    }
    index = (
        INDEX_HTML.replace("PAGE_CONFIG", json.dumps(page_config))
        .replace("DOC_NAME", doc_name)
        .replace("BASE_URL", base_url)
    )
    return index


INDEX_HTML = """\
<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>RetroLab - DOC_NAME</title>
  <link rel="icon" type="image/x-icon" href="/static/favicons/favicon-notebook.ico"
    class="favicon">
</head>
<body>
  <script id="jupyter-config-data" type="application/json">
    PAGE_CONFIG
  </script>
  <script src="BASE_URLstatic/retro/bundle.js" main="index"></script>
  <script type="text/javascript">
    /* Remove token from URL. */
    (function () {
      var parsedUrl = new URL(window.location.href);
      if (parsedUrl.searchParams.get('token')) {
        parsedUrl.searchParams.delete('token');
        window.history.replaceState({ }, '', parsedUrl.href);
      }
    })();
  </script>
</body>
</html>
"""

r = register_router(router)
