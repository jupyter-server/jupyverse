import json
from http import HTTPStatus
from pathlib import Path

import jupyterlab_js
from fastapi import Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_api.lab import Lab, PageConfig
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
        page_config: PageConfig,
    ) -> None:
        super().__init__(app, auth)

        self.jupyterlab_config = jupyterlab_config
        self.frontend_config = frontend_config
        self.lab = lab
        self.page_config = page_config
        lab.redirect_after_root = "lab"

        extensions_dir = lab.prefix_dir / "share" / "jupyter" / "labextensions"
        self.federated_extensions, self.disabled_extensions = lab.get_federated_extensions(
            extensions_dir
        )
        if jupyterlab_config.dev_mode:
            import jupyterlab as jupyterlab_module  # type: ignore

            jupyterlab_dir = Path(jupyterlab_module.__file__).parents[1]
            self.static_lab_dir = jupyterlab_dir / "dev_mode" / "static"
        else:
            self.static_lab_dir = lab.prefix_dir / "share" / "jupyter" / "lab" / "static"

        self.mount(
            "/static/lab",
            StaticFiles(directory=self.static_lab_dir),
            name="static",
        )

    async def get_lab(
        self,
        mode,
        user: User,
    ):
        return HTMLResponse(
            await self.get_index(
                "default",
                self.frontend_config.collaborative,
                self.jupyterlab_config.server_side_execution,
                self.jupyterlab_config.dev_mode,
                self.frontend_config.base_url,
                mode=mode,
            )
        )

    async def load_workspace(
        self,
        mode,
        path,
    ):
        return HTMLResponse(
            await self.get_index(
                "default",
                self.frontend_config.collaborative,
                self.jupyterlab_config.server_side_execution,
                self.jupyterlab_config.dev_mode,
                self.frontend_config.base_url,
                tree_path=path,
                mode=mode,
            )
        )

    async def get_workspace_data(self, user: User):
        if user:
            return json.loads(user.workspace)
        return {}

    async def set_workspace(
        self,
        request: Request,
        user: User,
        user_update,
    ):
        workspace = (await request.body()).decode("utf-8")
        await user_update({"workspace": workspace})
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def get_workspace(
        self,
        mode,
        name,
        path,
        user: User,
    ):
        return await self.get_index(
            name,
            self.frontend_config.collaborative,
            self.jupyterlab_config.server_side_execution,
            self.jupyterlab_config.dev_mode,
            self.frontend_config.base_url,
            tree_path=path,
            mode=mode,
        )

    async def get_index(
        self,
        workspace,
        collaborative,
        server_side_execution,
        dev_mode,
        base_url="/",
        tree_path=None,
        mode="lab",
    ):
        for path in self.static_lab_dir.glob("main.*.js"):
            main_id = path.name.split(".")[1]
            break
        vendor_id = None
        for path in (self.static_lab_dir).glob("vendors-node_modules_whatwg-fetch_fetch_js.*.js"):
            vendor_id = path.name.split(".")[1]
            break

        self.page_config.set(
            appName="JupyterLab",
            appNamespace="lab",
            appUrl="/lab",
            appVersion=jupyterlab_js.__version__,
            baseUrl=base_url,
            cacheFiles=False,
            collaborative=collaborative,
            serverSideExecution=server_side_execution,
            devMode=dev_mode,
            disabledExtensions=self.disabled_extensions,
            exposeAppInBrowser=False,
            extraLabextensionsPath=[],
            federated_extensions=self.federated_extensions,
            fullAppUrl=f"{base_url}lab",
            fullLabextensionsUrl=f"{base_url}lab/extensions",
            fullLicensesUrl=f"{base_url}lab/api/licenses",
            fullListingsUrl=f"{base_url}lab/api/listings",
            fullMathjaxUrl=f"{base_url}static/notebook/components/MathJax/MathJax.js",
            fullSettingsUrl=f"{base_url}lab/api/settings",
            fullStaticUrl=f"{base_url}static/lab",
            fullThemesUrl=f"{base_url}lab/api/themes",
            fullTranslationsApiUrl=f"{base_url}lab/api/translations",
            fullTreeUrl=f"{base_url}lab/tree",
            fullWorkspacesApiUrl=f"{base_url}lab/api/workspaces",
            ignorePlugins=[],
            labextensionsUrl="/lab/extensions",
            licensesUrl="/lab/api/licenses",
            listingsUrl="/lab/api/listings",
            mathjaxConfig="TeX-AMS-MML_HTMLorMML-full,Safe",
            mode="multiple-document" if mode == "lab" else "single-document",
            notebookVersion="[1, 9, 0]",
            quitButton=True,
            settingsUrl="/lab/api/settings",
            store_id=0,
            schemasDir=(self.lab.prefix_dir / "share" / "jupyter" / "lab" / "schemas").as_posix(),
            terminalsAvailable=True,
            themesDir=(self.lab.prefix_dir / "share" / "jupyter" / "lab" / "themes").as_posix(),
            themesUrl="/lab/api/themes",
            token="4e2804532de366abc81e32ab0c6bf68a73716fafbdbb2098",
            translationsApiUrl="/lab/api/translations",
            treePath="" if tree_path is None else tree_path,
            workspace=workspace,
            treeUrl="/lab/tree",
            workspacesApiUrl="/lab/api/workspaces",
            wsUrl="",
        )
        _page_config = await self.page_config.get()
        index = (
            INDEX_HTML.replace("PAGE_CONFIG", json.dumps(_page_config))
            .replace("FULL_STATIC_URL", _page_config["fullStaticUrl"])
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
