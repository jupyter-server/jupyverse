import json
from html import escape
from html.parser import HTMLParser
from http import HTTPStatus
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

from fastapi import Response
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jupyverse_api import App
from jupyverse_auth import Auth, User
from jupyverse_frontend import FrontendConfig
from jupyverse_jupyterlab import JupyterLab, JupyterLabConfig
from jupyverse_lab import Lab, PageConfig
from starlette.requests import Request

from .index import INDEX_HTML

CWD = Path.cwd()


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.scripts: list[list[tuple[str, str | None]]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script" and any(name == "src" for name, _ in attrs):
            self.scripts.append(attrs)


def _render_static_scripts(static_lab_dir: Path, full_static_url: str) -> str:
    index_path = static_lab_dir / "index.html"
    if not index_path.is_file():
        raise FileNotFoundError(f"JupyterLab static index does not exist: {index_path}")

    parser = _ScriptParser()
    parser.feed(index_path.read_text(encoding="utf-8"))
    rendered_scripts = []
    has_main = False

    for attrs in parser.scripts:
        source = next(value for name, value in attrs if name == "src")
        if source is None:
            raise ValueError(f"JupyterLab static index has an empty script source: {index_path}")

        parsed_source = urlsplit(source)
        decoded_path = unquote(parsed_source.path)
        source_path = PurePosixPath(decoded_path)
        if (
            parsed_source.scheme
            or parsed_source.netloc
            or "\\" in decoded_path
            or ".." in source_path.parts
        ):
            raise ValueError(f"JupyterLab static index has a non-local script source: {source}")

        asset_name = source_path.name
        asset_path = static_lab_dir / asset_name
        if not asset_name or not asset_path.is_file():
            raise FileNotFoundError(
                f"JupyterLab static index references a missing script: {asset_path}"
            )

        if asset_name.startswith("main.") and asset_name.endswith(".js"):
            has_main = True

        query = f"?{parsed_source.query}" if parsed_source.query else ""
        fragment = f"#{parsed_source.fragment}" if parsed_source.fragment else ""
        local_source = f"{full_static_url.rstrip('/')}/{asset_name}{query}{fragment}"
        rendered_attrs = []
        for name, value in attrs:
            value = local_source if name == "src" else value
            rendered_attrs.append(
                name if value is None else f'{name}="{escape(value, quote=True)}"'
            )
        rendered_scripts.append(f"<script {' '.join(rendered_attrs)}></script>")

    if not has_main:
        raise RuntimeError(f"JupyterLab static index has no main entry point: {index_path}")

    return "\n".join(rendered_scripts)


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
            import jupyterlab_js as jupyterlab_module  # type: ignore

            self.static_lab_dir = lab.prefix_dir / "share" / "jupyter" / "lab" / "static"
        self._jupyterlab_module = jupyterlab_module

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
        self.page_config.set(
            appName="JupyterLab",
            appNamespace="lab",
            appUrl="/lab",
            appVersion=self._jupyterlab_module.__version__,
            baseUrl=base_url,
            cacheFiles=False,
            collaborative=collaborative,
            serverSideExecution=server_side_execution,
            devMode=dev_mode,
            disabledExtensions=self.disabled_extensions,
            exposeAppInBrowser=False,
            extraLabextensionsPath=[],
            federated_extensions=self.federated_extensions,
            rootUri=f"file://{CWD}",
            virtualDocumentsUri=f"file://{CWD / '.virtual_documents'}",
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
        static_scripts = _render_static_scripts(
            self.static_lab_dir,
            _page_config["fullStaticUrl"],
        )
        index = INDEX_HTML.replace("PAGE_CONFIG", json.dumps(_page_config)).replace(
            "STATIC_SCRIPTS", static_scripts
        )
        return index
