import json
from pathlib import Path
import sys
from glob import glob
from http import HTTPStatus

import jupyterlab  # type: ignore
import jupyverse  # type: ignore
from fastapi import APIRouter, Response, Depends
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request  # type: ignore
from fps.config import Config  # type: ignore
from fps.hooks import register_router  # type: ignore

from fps_auth.routes import users, user_db  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_auth.config import AuthConfig  # type: ignore

from .config import JupyterLabConfig

router = APIRouter()
prefix_dir: Path = Path(sys.prefix)
jlab_config = Config(JupyterLabConfig)
auth_config = Config(AuthConfig)

router.mount(
    "/static/lab",
    StaticFiles(directory=prefix_dir / "share" / "jupyter" / "lab" / "static"),
    name="static",
)

router.mount(
    "/lab/api/themes",
    StaticFiles(directory=prefix_dir / "share" / "jupyter" / "lab" / "themes"),
    name="themes",
)

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


@router.get("/")
async def get_root():
    return RedirectResponse("/lab")


@router.get("/lab")
async def get_lab():
    return HTMLResponse(get_index("default", jlab_config.collaborative))


@router.get("/lab/tree/{path:path}")
async def load_workspace(path):
    return HTMLResponse(get_index("default", jlab_config.collaborative))


@router.get("/favicon.ico")
async def get_favicon():
    return FileResponse(Path(jupyverse.__file__).parent / "static" / "favicon.ico")


@router.get("/static/notebook/components/MathJax/{rest_of_path:path}")
async def get_mathjax(rest_of_path):
    return RedirectResponse(
        "https://cdnjs.cloudflare.com/ajax/libs/mathjax/2.7.7/" + rest_of_path
    )


@router.get("/lab/api/listings/@jupyterlab/extensionmanager-extension/listings.json")
async def get_listings():
    return {
        "blocked_extensions_uris": [],
        "allowed_extensions_uris": [],
        "blocked_extensions": [],
        "allowed_extensions": [],
    }


@router.get("/lab/api/workspaces/{name}")
async def get_workspace_data(user: User = Depends(users.current_user(optional=True))):
    if user and user.workspace:
        return json.loads(user.workspace)
    return {}


@router.put(
    "/lab/api/workspaces/{name}",
    status_code=204,
)
async def set_workspace(
    request: Request,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    user.workspace = await request.body()
    await user_db.update(user)
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.get("/lab/workspaces/{name}", response_class=HTMLResponse)
async def get_workspace(
    name, user: User = Depends(users.current_user(optional=auth_config.disable_auth))
):
    return get_index(name, jlab_config.collaborative)


@router.get("/lab/api/translations")
async def get_translations():
    return {}


@router.get("/lab/api/translations/{language}")
async def get_translation(
    language,
):
    return {}


@router.get("/lab/api/settings/{name0}/{name1}:{name2}")
async def get_setting(
    name0,
    name1,
    name2,
    user: User = Depends(users.current_user(optional=True)),
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
    if user and user.settings:
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
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    if user and user.settings:
        settings = json.loads(user.settings)
    else:
        settings = {}
    settings[f"{name0}:{name1}"] = await request.json()
    user.settings = json.dumps(settings)
    await user_db.update(user)
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.get("/lab/api/settings")
async def get_settings(user: User = Depends(users.current_user(optional=True))):
    with open(
        prefix_dir / "share" / "jupyter" / "lab" / "static" / "package.json"
    ) as f:
        package = json.load(f)
    if user and user.settings:
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


INDEX_HTML = """\
<!doctype html><html lang="en"><head><meta charset="utf-8"><title>JupyterLab</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script id="jupyter-config-data" type="application/json">PAGE_CONFIG</script>
<script defer="defer" src="FULL_STATIC_URL/main.MAIN_ID.js?v=MAIN_ID"
></script></head><body><script>/* Remove token from URL. */
  (function () {
    var location = window.location;
    var search = location.search;

    // If there is no query string, bail.
    if (search.length <= 1) {
      return;
    }

    // Rebuild the query string without the `token`.
    var query = '?' + search.slice(1).split('&')
      .filter(function (param) { return param.split('=')[0] !== 'token'; })
      .join('&');

    // Rebuild the URL with the new query string.
    var url = location.origin + location.pathname +
      (query !== '?' ? query : '') + location.hash;

    if (url === location.href) {
      return;
    }

    window.history.replaceState({ }, '', url);
  })();</script></body></html>
"""


def get_index(workspace, collaborative):
    for path in (prefix_dir / "share" / "jupyter" / "lab" / "static").glob("main.*.js"):
        main_id = path.name.split(".")[1]
        break
    base_url = "/"
    full_static_url = "/static/lab"
    page_config = {
        "appName": "JupyterLab",
        "appNamespace": "lab",
        "appUrl": "/lab",
        "appVersion": jupyterlab.__version__,
        "baseUrl": base_url,
        "cacheFiles": False,
        "collaborative": collaborative,
        "disabledExtensions": [],
        "exposeAppInBrowser": False,
        "extraLabextensionsPath": [],
        "federated_extensions": federated_extensions,
        "fullAppUrl": "/lab",
        "fullLabextensionsUrl": "/lab/extensions",
        "fullLicensesUrl": "/lab/api/licenses",
        "fullListingsUrl": "/lab/api/listings",
        "fullMathjaxUrl": "/static/notebook/components/MathJax/MathJax.js",
        "fullSettingsUrl": "/lab/api/settings",
        "fullStaticUrl": full_static_url,
        "fullThemesUrl": "/lab/api/themes",
        "fullTranslationsApiUrl": "/lab/api/translations",
        "fullTreeUrl": "/lab/tree",
        "fullWorkspacesApiUrl": "/lab/api/workspaces",
        "ignorePlugins": [],
        "labextensionsUrl": "/lab/extensions",
        "licensesUrl": "/lab/api/licenses",
        "listingsUrl": "/lab/api/listings",
        "mathjaxConfig": "TeX-AMS-MML_HTMLorMML-full,Safe",
        "mode": "multiple-document",
        "notebookVersion": "[1, 9, 0]",
        "quitButton": True,
        "settingsUrl": "/lab/api/settings",
        "store_id": 0,
        "schemasDir": str(prefix_dir / "share" / "jupyter" / "lab" / "schemas"),
        "terminalsAvailable": True,
        "themesDir": str(prefix_dir / "share" / "jupyter" / "lab" / "themes"),
        "themesUrl": "/lab/api/themes",
        "token": "4e2804532de366abc81e32ab0c6bf68a73716fafbdbb2098",
        "translationsApiUrl": "/lab/api/translations",
        "treePath": "",
        "workspace": workspace,
        "treeUrl": "/lab/tree",
        "workspacesApiUrl": "/lab/api/workspaces",
        "wsUrl": "",
    }
    index = (
        INDEX_HTML.replace("PAGE_CONFIG", json.dumps(page_config))
        .replace("BASE_URL", base_url)
        .replace("FULL_STATIC_URL", full_static_url)
        .replace("MAIN_ID", main_id)
    )
    return index


r = register_router(router)
