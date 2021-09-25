import json
from http import HTTPStatus

import jupyterlab  # type: ignore
from fastapi import APIRouter, Response, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request  # type: ignore
from fps.hooks import register_router  # type: ignore

from fps_auth.db import get_user_db  # type: ignore
from fps_auth.backends import current_user  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_lab.routes import init_router  # type: ignore

from fps_lab.config import get_lab_config  # type: ignore

router = APIRouter()
prefix_dir, federated_extensions = init_router(router, "lab")

router.mount(
    "/static/lab",
    StaticFiles(directory=prefix_dir / "share" / "jupyter" / "lab" / "static"),
    name="static",
)


@router.get("/lab")
async def get_lab(
    user: User = Depends(current_user()), lab_config=Depends(get_lab_config)
):
    return HTMLResponse(
        get_index("default", lab_config.collaborative, lab_config.base_url)
    )


@router.get("/lab/tree/{path:path}")
async def load_workspace(path, lab_config=Depends(get_lab_config)):
    return HTMLResponse(
        get_index("default", lab_config.collaborative, lab_config.base_url)
    )


@router.get("/lab/api/workspaces/{name}")
async def get_workspace_data(user: User = Depends(current_user())):
    if user:
        return json.loads(user.workspace)
    return {}


@router.put(
    "/lab/api/workspaces/{name}",
    status_code=204,
)
async def set_workspace(
    request: Request,
    user: User = Depends(current_user()),
    user_db=Depends(get_user_db),
):
    user.workspace = await request.body()
    await user_db.update(user)
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.get("/lab/workspaces/{name}", response_class=HTMLResponse)
async def get_workspace(
    name, user: User = Depends(current_user()), lab_config=Depends(get_lab_config)
):
    return get_index(name, lab_config.collaborative, lab_config.base_url)


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


def get_index(workspace, collaborative, base_url="/"):
    for path in (prefix_dir / "share" / "jupyter" / "lab" / "static").glob("main.*.js"):
        main_id = path.name.split(".")[1]
        break
    full_static_url = f"{base_url}static/lab"
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
        "fullAppUrl": f"{base_url}lab",
        "fullLabextensionsUrl": f"{base_url}lab/extensions",
        "fullLicensesUrl": f"{base_url}lab/api/licenses",
        "fullListingsUrl": f"{base_url}lab/api/listings",
        "fullMathjaxUrl": f"{base_url}static/notebook/components/MathJax/MathJax.js",
        "fullSettingsUrl": f"{base_url}lab/api/settings",
        "fullStaticUrl": full_static_url,
        "fullThemesUrl": f"{base_url}lab/api/themes",
        "fullTranslationsApiUrl": f"{base_url}lab/api/translations",
        "fullTreeUrl": f"{base_url}lab/tree",
        "fullWorkspacesApiUrl": f"{base_url}lab/api/workspaces",
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
        .replace("FULL_STATIC_URL", full_static_url)
        .replace("MAIN_ID", main_id)
    )
    return index


r = register_router(router)
