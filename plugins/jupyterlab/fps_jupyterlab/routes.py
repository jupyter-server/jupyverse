import json
from http import HTTPStatus
from pathlib import Path

import jupyterlab as jupyterlab_module  # type: ignore
from fastapi import APIRouter, Depends, Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_api.lab import Lab
from starlette.requests import Request

from .index import INDEX_HTML


class _JupyterLab(JupyterLab):
    def __init__(
        self,
        app: App,
        jupyterlab_config: JupyterLabConfig,
        auth: Auth,
        frontend_config: FrontendConfig,
        lab: Lab,
    ) -> None:
        super().__init__(app)

        router = APIRouter()
        self.prefix_dir, federated_extensions = lab.init_router(router, "lab")
        extensions_dir = self.prefix_dir / "share" / "jupyter" / "labextensions"
        self.federated_extensions, self.disabled_extension = lab.get_federated_extensions(
            extensions_dir
        )
        jupyterlab_dir = Path(jupyterlab_module.__file__).parents[1]

        if jupyterlab_config.dev_mode:
            self.static_lab_dir = jupyterlab_dir / "dev_mode" / "static"
        else:
            self.static_lab_dir = self.prefix_dir / "share" / "jupyter" / "lab" / "static"

        self.mount(
            "/static/lab",
            StaticFiles(directory=self.static_lab_dir),
            name="static",
        )

        @router.get("/lab")
        async def get_lab(
            user: User = Depends(auth.current_user()),
        ):
            return HTMLResponse(
                self.get_index(
                    "default",
                    frontend_config.collaborative,
                    jupyterlab_config.dev_mode,
                    frontend_config.base_url,
                )
            )

        @router.get("/lab/tree/{path:path}")
        async def load_workspace(
            path,
        ):
            return HTMLResponse(
                self.get_index(
                    "default",
                    frontend_config.collaborative,
                    jupyterlab_config.dev_mode,
                    frontend_config.base_url,
                )
            )

        @router.get("/lab/api/workspaces/{name}")
        async def get_workspace_data(user: User = Depends(auth.current_user())):
            if user:
                return json.loads(user.workspace)
            return {}

        @router.put(
            "/lab/api/workspaces/{name}",
            status_code=204,
        )
        async def set_workspace(
            request: Request,
            user: User = Depends(auth.current_user()),
            user_update=Depends(auth.update_user),
        ):
            workspace = (await request.body()).decode("utf-8")
            await user_update({"workspace": workspace})
            return Response(status_code=HTTPStatus.NO_CONTENT.value)

        @router.get("/lab/workspaces/{name}", response_class=HTMLResponse)
        async def get_workspace(
            name,
            user: User = Depends(auth.current_user()),
        ):
            return self.get_index(
                name,
                frontend_config.collaborative,
                jupyterlab_config.dev_mode,
                frontend_config.base_url,
            )

        self.include_router(router)

    def get_index(self, workspace, collaborative, dev_mode, base_url="/"):
        for path in (self.static_lab_dir).glob("main.*.js"):
            main_id = path.name.split(".")[1]
            break
        vendor_id = None
        for path in (self.static_lab_dir).glob("vendors-node_modules_whatwg-fetch_fetch_js.*.js"):
            vendor_id = path.name.split(".")[1]
            break
        full_static_url = f"{base_url}static/lab"

        page_config = {
            "appName": "JupyterLab",
            "appNamespace": "lab",
            "appUrl": "/lab",
            "appVersion": jupyterlab_module.__version__,
            "baseUrl": base_url,
            "cacheFiles": False,
            "collaborative": collaborative,
            "devMode": dev_mode,
            "disabledExtensions": self.disabled_extension,
            "exposeAppInBrowser": False,
            "extraLabextensionsPath": [],
            "federated_extensions": self.federated_extensions,
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
            "schemasDir": (self.prefix_dir / "share" / "jupyter" / "lab" / "schemas").as_posix(),
            "terminalsAvailable": True,
            "themesDir": (self.prefix_dir / "share" / "jupyter" / "lab" / "themes").as_posix(),
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
        if vendor_id:
            index = index.replace(
                "VENDORS_NODE_MODULES",
                '<script defer src="/static/lab/vendors-node_modules_whatwg-fetch_fetch_js.'
                f'{vendor_id}.js"></script>',
            )
        else:
            index = index.replace("VENDORS_NODE_MODULES", "")
        return index
