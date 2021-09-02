import json
import pathlib
import sys
from http import HTTPStatus

from fps.config import Config  # type: ignore
from fps.hooks import register_router  # type: ignore
import retrolab  # type: ignore
from fastapi import APIRouter, Response, Depends
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from fps_auth.routes import users  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_auth.config import AuthConfig  # type: ignore

router = APIRouter()
auth_config = Config(AuthConfig)
retrolab_dir = pathlib.Path(retrolab.__file__).parent
prefix_dir = pathlib.Path(sys.prefix)

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


@router.get("/")
async def get_root():
    return RedirectResponse("/retro/tree")


@router.get("/retro/tree", response_class=HTMLResponse)
async def get_tree():
    return get_index("Tree", "tree")


@router.get("/retro/notebooks/{name}", response_class=HTMLResponse)
async def get_notebook(
    name: str,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    return get_index(name, "notebook")


@router.get("/lab/api/settings/@jupyterlab/{name0}:{name1}")
async def get_setting(
    name0,
    name1,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    with open(
        prefix_dir
        / "share"
        / "jupyter"
        / "lab"
        / "schemas"
        / "@jupyterlab"
        / name0
        / f"{name1}.json"
    ) as f:
        schema = json.load(f)
    return {
        "id": f"@jupyterlab/{name0}:{name1}",
        "schema": schema,
        "version": "3.1.0-rc.1",
        "raw": "{}",
        "settings": {},
        "last_modified": None,
        "created": None,
    }


@router.put(
    "/lab/api/settings/@jupyterlab/{name0}:{name1}",
    status_code=204,
)
async def change_setting(
    name0,
    name1,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    # TODO
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.get("/lab/api/settings")
async def get_settings(
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    settings = []
    for path in (
        prefix_dir / "share" / "jupyter" / "lab" / "schemas" / "@jupyterlab"
    ).glob("*/*.json"):
        with open(path) as f:
            schema = json.load(f)
        setting = {
            "id": f"@jupyterlab/{path.parent.name}:{path.stem}",
            "schema": schema,
            "version": "3.1.0-rc.1",
            "raw": "{}",
            "settings": {},
            "warning": None,
            "last_modified": None,
            "created": None,
        }
        settings.append(setting)
    return {"settings": settings}


def get_index(doc_name, retro_page):
    for path in (retrolab_dir / "labextension" / "static").glob("remoteEntry.*.js"):
        load = f"static/{path.name}"
        break

    page_config = {
        "appName": "RetroLab",
        "appNamespace": "retro",
        "appSettingsDir": str(prefix_dir / "share" / "jupyter" / "lab" / "settings"),
        "appUrl": "/lab",
        "appVersion": retrolab.__version__,
        "baseUrl": "/",
        "cacheFiles": True,
        "disabledExtensions": [],
        "extraLabextensionsPath": [],
        "federated_extensions": [
            {
                "extension": "./extension",
                "load": load,
                "name": "@retrolab/lab-extension",
                "style": "./style",
            }
        ],
        "frontendUrl": "/retro/",
        "fullAppUrl": "/lab",
        "fullLabextensionsUrl": "/lab/extensions",
        "fullLicensesUrl": "/lab/api/licenses",
        "fullListingsUrl": "/lab/api/listings",
        "fullMathjaxUrl": "/static/notebook/components/MathJax/MathJax.js",
        "fullSettingsUrl": "/lab/api/settings",
        "fullStaticUrl": "/static/retro",
        "fullThemesUrl": "/lab/api/themes",
        "fullTranslationsApiUrl": "/lab/api/translations",
        "fullTreeUrl": "/lab/tree",
        "fullWorkspacesApiUrl": "/lab/api/workspaces",
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
    index = INDEX_HTML.replace("PAGE_CONFIG", json.dumps(page_config)).replace(
        "DOC_NAME", doc_name
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
  <script src="/static/retro/bundle.js" main="index"></script>
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
