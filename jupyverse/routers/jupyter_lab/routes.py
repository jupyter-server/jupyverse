import json
import pathlib
import pkgutil
from http import HTTPStatus

from fastapi import Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

import jupyterlab  # type: ignore

from jupyverse import JAPIRouter


def init(jupyverse):
    router.init(jupyverse)
    return router


class JupyterLabRouter(JAPIRouter):
    def init(self, jupyverse):
        self.jupyverse = jupyverse

        retrolab_package = pkgutil.get_loader("retrolab")
        self.retrolab_dir = pathlib.Path(retrolab_package.path).parent

        self.jupyverse.app.mount(
            "/static/lab",
            StaticFiles(
                directory=self.prefix_dir / "share" / "jupyter" / "lab" / "static"
            ),
            name="static",
        )
        self.jupyverse.app.mount(
            "/lab/api/themes",
            StaticFiles(
                directory=self.prefix_dir / "share" / "jupyter" / "lab" / "themes"
            ),
            name="themes",
        )
        self.jupyverse.app.include_router(router)


router = JupyterLabRouter()


@router.get("/", response_class=HTMLResponse)
async def get_tree():
    for path in (router.prefix_dir / "share" / "jupyter" / "lab" / "static").glob(
        "main.*.js"
    ):
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
        "disabledExtensions": [],
        "exposeAppInBrowser": False,
        "extraLabextensionsPath": [],
        "federated_extensions": [],
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
        # "labextensionsPath": [
        #    str(router.prefix_dir / "share" / "jupyter" / "labextensions")
        # ],
        "labextensionsUrl": "/lab/extensions",
        "licensesUrl": "/lab/api/licenses",
        "listingsUrl": "/lab/api/listings",
        "mathjaxConfig": "TeX-AMS-MML_HTMLorMML-full,Safe",
        "mode": "multiple-document",
        "notebookVersion": "[1, 9, 0]",
        "quitButton": True,
        "settingsUrl": "/lab/api/settings",
        "store_id": 0,
        "terminalsAvailable": True,
        "schemasDir": str(router.prefix_dir / "share" / "jupyter" / "lab" / "schemas"),
        "terminalsAvailable": True,
        "themesDir": str(router.prefix_dir / "share" / "jupyter" / "lab" / "themes"),
        "themesUrl": "/lab/api/themes",
        "token": "4e2804532de366abc81e32ab0c6bf68a73716fafbdbb2098",
        "translationsApiUrl": "/lab/api/translations",
        "treePath": "",
        "workspace": "default",
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


@router.get("/retro/notebooks/{name}", response_class=HTMLResponse)
async def get_notebook(name: str):
    return get_index(name, "notebook")


@router.get("/api/terminals")
async def get_terminals():
    return []


@router.get("/lab/api/translations")
async def get_translations():
    return {}


@router.get("/lab/api/translations/{language}")
async def get_translation(language):
    return {}


@router.get("/lab/api/settings/@jupyterlab/{name0}:{name1}")
async def get_setting(name0, name1):
    with open(
        router.prefix_dir
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
async def change_setting(name0, name1):
    # TODO
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.get("/lab/api/settings")
async def get_settings():
    settings = []
    for path in (
        router.prefix_dir / "share" / "jupyter" / "lab" / "schemas" / "@jupyterlab"
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
    for path in (router.retrolab_dir / "labextension" / "static").glob(
        "remoteEntry.*.js"
    ):
        load = f"static/{path.name}"
        break

    page_config = {
        "appName": "RetroLab",
        "appNamespace": "retro",
        "appSettingsDir": str(
            router.prefix_dir / "share" / "jupyter" / "lab" / "settings"
        ),
        "appUrl": "/lab",
        "appVersion": "0.2.2",
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
        "labextensionsPath": [
            str(router.prefix_dir / "share" / "jupyter" / "labextensions")
        ],
        "labextensionsUrl": "/lab/extensions",
        "licensesUrl": "/lab/api/licenses",
        "listingsUrl": "/lab/api/listings",
        "mathjaxConfig": "TeX-AMS-MML_HTMLorMML-full,Safe",
        "retroLogo": False,
        "retroPage": retro_page,
        "schemasDir": str(router.prefix_dir / "share" / "jupyter" / "lab" / "schemas"),
        "settingsUrl": "/lab/api/settings",
        "staticDir": str(router.retrolab_dir / "static"),
        "templatesDir": str(router.retrolab_dir / "templates"),
        "terminalsAvailable": True,
        "themesDir": str(router.prefix_dir / "share" / "jupyter" / "lab" / "themes"),
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
