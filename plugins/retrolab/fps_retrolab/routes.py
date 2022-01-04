import json
from pathlib import Path

from fps.hooks import register_router  # type: ignore
import retrolab  # type: ignore
from fastapi import APIRouter, Depends
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from fps_auth.backends import current_user  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_auth.config import get_auth_config  # type: ignore

from fps_lab.routes import init_router  # type: ignore
from fps_lab.config import get_lab_config  # type: ignore
from fps_lab.utils import get_federated_extensions  # type: ignore

router = APIRouter()
prefix_dir, federated_extensions = init_router(router, "retro/tree")
retrolab_dir = Path(retrolab.__file__).parent

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

for path in (retrolab_dir / "labextension" / "static").glob("remoteEntry.*.js"):
    load = f"static/{path.name}"
    break
retro_federated_extensions = [
    {
        "extension": "./extension",
        "load": load,
        "name": "@retrolab/lab-extension",
        "style": "./style",
    }
]


@router.get("/retro/tree", response_class=HTMLResponse)
async def get_tree(
    user: User = Depends(current_user),
    lab_config=Depends(get_lab_config),
    auth_config=Depends(get_auth_config),
):
    return get_index("Tree", "tree", auth_config.collaborative, lab_config.base_url)


@router.get("/retro/notebooks/{path:path}", response_class=HTMLResponse)
async def get_notebook(
    path,
    user: User = Depends(current_user),
    lab_config=Depends(get_lab_config),
    auth_config=Depends(get_auth_config),
):
    return get_index(path, "notebooks", auth_config.collaborative, lab_config.base_url)


@router.get("/retro/edit/{path:path}", response_class=HTMLResponse)
async def edit_file(
    path,
    user: User = Depends(current_user),
    lab_config=Depends(get_lab_config),
    auth_config=Depends(get_auth_config),
):
    return get_index(path, "edit", auth_config.collaborative, lab_config.base_url)


@router.get("/retro/consoles/{path:path}", response_class=HTMLResponse)
async def get_console(
    path,
    user: User = Depends(current_user),
    lab_config=Depends(get_lab_config),
    auth_config=Depends(get_auth_config),
):
    return get_index(path, "consoles", auth_config.collaborative, lab_config.base_url)


@router.get("/retro/terminals/{name}", response_class=HTMLResponse)
async def get_terminal(
    name: str,
    user: User = Depends(current_user),
    lab_config=Depends(get_lab_config),
    auth_config=Depends(get_auth_config),
):
    return get_index(name, "terminals", auth_config.collaborative, lab_config.base_url)


def get_index(doc_name, retro_page, collaborative, base_url="/"):
    extensions_dir = prefix_dir / "share" / "jupyter" / "labextensions"
    federated_extensions, disabled_extension = get_federated_extensions(extensions_dir)
    page_config = {
        "appName": "RetroLab",
        "appNamespace": "retro",
        "appSettingsDir": str(prefix_dir / "share" / "jupyter" / "lab" / "settings"),
        "appUrl": "/lab",
        "appVersion": retrolab.__version__,
        "baseUrl": base_url,
        "cacheFiles": True,
        "collaborative": collaborative,
        "disabledExtensions": disabled_extension,
        "extraLabextensionsPath": [],
        "federated_extensions": retro_federated_extensions + federated_extensions,
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
