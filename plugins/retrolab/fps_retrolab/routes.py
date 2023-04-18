import json
from pathlib import Path

import retrolab  # type: ignore
from fastapi.staticfiles import StaticFiles
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.lab import Lab
from jupyverse_api.retrolab import RetroLab


class _RetroLab(RetroLab):
    def __init__(self, app: App, auth: Auth, frontend_config: FrontendConfig, lab: Lab) -> None:
        super().__init__(app, auth, lab)
        self.frontend_config = frontend_config
        self.lab = lab
        self.lab.redirect_after_root = "retro/tree"

        self.retrolab_dir = Path(retrolab.__file__).parent

        self.mount(
            "/static/retro",
            StaticFiles(directory=self.retrolab_dir / "static"),
            name="static",
        )

        for path in (self.retrolab_dir / "labextension" / "static").glob("remoteEntry.*.js"):
            load = f"static/{path.name}"
            break

        self.retro_federated_extensions = [
            {
                "extension": "./extension",
                "load": load,
                "name": "@retrolab/lab-extension",
                "style": "./style",
            }
        ]

    async def get_tree(
        self,
        user: User,
    ):
        return get_index(
            self.lab,
            self.retrolab_dir,
            self.retro_federated_extensions,
            "Tree",
            "tree",
            self.frontend_config.collaborative,
            self.frontend_config.base_url,
        )

    async def get_notebook(
        self,
        path,
        user: User,
    ):
        return get_index(
            self.lab,
            self.retrolab_dir,
            self.retro_federated_extensions,
            path,
            "notebooks",
            self.frontend_config.collaborative,
            self.frontend_config.base_url,
        )

    async def edit_file(
        self,
        path,
        user: User,
    ):
        return get_index(
            self.lab,
            self.retrolab_dir,
            self.retro_federated_extensions,
            path,
            "edit",
            self.frontend_config.collaborative,
            self.frontend_config.base_url,
        )

    async def get_console(
        self,
        path,
        user: User,
    ):
        return get_index(
            self.lab,
            self.retrolab_dir,
            self.retro_federated_extensions,
            path,
            "consoles",
            self.frontend_config.collaborative,
            self.frontend_config.base_url,
        )

    async def get_terminal(
        self,
        name: str,
        user: User,
    ):
        return get_index(
            self.lab,
            self.retrolab_dir,
            self.retro_federated_extensions,
            name,
            "terminals",
            self.frontend_config.collaborative,
            self.frontend_config.base_url,
        )


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


def get_index(
    lab, retrolab_dir, retro_federated_extensions, doc_name, retro_page, collaborative, base_url="/"
):
    extensions_dir = lab.prefix_dir / "share" / "jupyter" / "labextensions"
    federated_extensions, disabled_extension = lab.get_federated_extensions(extensions_dir)
    page_config = {
        "appName": "RetroLab",
        "appNamespace": "retro",
        "appSettingsDir": (lab.prefix_dir / "share" / "jupyter" / "lab" / "settings").as_posix(),
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
        "labextensionsPath": [(lab.prefix_dir / "share" / "jupyter" / "labextensions").as_posix()],
        "labextensionsUrl": "/lab/extensions",
        "licensesUrl": "/lab/api/licenses",
        "listingsUrl": "/lab/api/listings",
        "mathjaxConfig": "TeX-AMS-MML_HTMLorMML-full,Safe",
        "retroLogo": False,
        "retroPage": retro_page,
        "schemasDir": (lab.prefix_dir / "share" / "jupyter" / "lab" / "schemas").as_posix(),
        "settingsUrl": "/lab/api/settings",
        "staticDir": (retrolab_dir / "static").as_posix(),
        "templatesDir": (retrolab_dir / "templates").as_posix(),
        "terminalsAvailable": True,
        "themesDir": (lab.prefix_dir / "share" / "jupyter" / "lab" / "themes").as_posix(),
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
