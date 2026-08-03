import json
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import unquote, urlsplit

import notebook_frontend
from fastapi.staticfiles import StaticFiles
from jupyverse_api import App
from jupyverse_auth import Auth, User
from jupyverse_frontend import FrontendConfig
from jupyverse_lab import Lab, PageConfig
from jupyverse_notebook import Notebook

CWD = Path.cwd()


class _ScriptParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.sources: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "script":
            self.sources.extend(
                value for name, value in attrs if name == "src" and value is not None
            )


def _get_main_id(notebook_dir: Path, notebook_page: str) -> str:
    template_path = notebook_dir / "templates" / f"{notebook_page}.html"
    if not template_path.is_file():
        raise FileNotFoundError(f"Notebook template does not exist: {template_path}")

    parser = _ScriptParser()
    parser.feed(template_path.read_text(encoding="utf-8"))

    for source in parser.sources:
        parsed_source = urlsplit(source)
        decoded_path = unquote(parsed_source.path)
        source_path = PurePosixPath(decoded_path)
        if (
            parsed_source.scheme
            or parsed_source.netloc
            or "\\" in decoded_path
            or ".." in source_path.parts
        ):
            raise ValueError(f"Notebook template has a non-local script source: {source}")

        asset_name = source_path.name
        if asset_name.startswith("main.") and asset_name.endswith(".js"):
            asset_path = notebook_dir / "static" / asset_name
            if not asset_path.is_file():
                raise FileNotFoundError(
                    f"Notebook template references a missing script: {asset_path}"
                )
            return asset_name.removeprefix("main.").removesuffix(".js")

    raise RuntimeError(f"Notebook template has no main entry point: {template_path}")


class _Notebook(Notebook):
    def __init__(
        self,
        app: App,
        auth: Auth,
        frontend_config: FrontendConfig,
        lab: Lab,
        page_config: PageConfig,
    ) -> None:
        super().__init__(app, auth)
        self.frontend_config = frontend_config
        self.lab = lab
        self.page_config = page_config
        lab.redirect_after_root = "tree"

        extensions_dir = lab.prefix_dir / "share" / "jupyter" / "labextensions"
        self.federated_extensions, self.disabled_extensions = lab.get_federated_extensions(
            extensions_dir
        )
        self.notebook_dir = Path(notebook_frontend.__file__).parent

        self.mount(
            "/static/notebook",
            StaticFiles(directory=self.notebook_dir / "static"),
            name="static",
        )

    async def get_tree(
        self,
        user: User,
    ):
        return await self.get_index(
            self.lab,
            self.notebook_dir,
            self.federated_extensions,
            self.disabled_extensions,
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
        return await self.get_index(
            self.lab,
            self.notebook_dir,
            self.federated_extensions,
            self.disabled_extensions,
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
        return await self.get_index(
            self.lab,
            self.notebook_dir,
            self.federated_extensions,
            self.disabled_extensions,
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
        return await self.get_index(
            self.lab,
            self.notebook_dir,
            self.federated_extensions,
            self.disabled_extensions,
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
        return await self.get_index(
            self.lab,
            self.notebook_dir,
            self.federated_extensions,
            self.disabled_extensions,
            name,
            "terminals",
            self.frontend_config.collaborative,
            self.frontend_config.base_url,
        )

    async def get_index(
        self,
        lab,
        notebook_dir,
        federated_extensions,
        disabled_extensions,
        doc_name,
        notebook_page,
        collaborative,
        base_url="/",
    ):
        main_id = _get_main_id(notebook_dir, notebook_page)
        self.page_config.set(
            appName="Notebook",
            appNamespace="notebook",
            appSettingsDir=(lab.prefix_dir / "share" / "jupyter" / "lab" / "settings").as_posix(),
            appUrl="/lab",
            appVersion=notebook_frontend.__version__,
            baseUrl=base_url,
            cacheFiles=True,
            collaborative=collaborative,
            disabledExtensions=disabled_extensions,
            extraLabextensionsPath=[],
            federated_extensions=federated_extensions,
            rootUri=f"file://{CWD}",
            virtualDocumentsUri=f"file://{CWD / '.virtual_documents'}",
            frontendUrl="/notebook/",
            fullAppUrl=f"{base_url}lab",
            fullLabextensionsUrl=f"{base_url}lab/extensions",
            fullLicensesUrl=f"{base_url}lab/api/licenses",
            fullListingsUrl=f"{base_url}lab/api/listings",
            fullMathjaxUrl=f"{base_url}static/notebook/components/MathJax/MathJax.js",
            fullSettingsUrl=f"{base_url}lab/api/settings",
            fullStaticUrl=f"{base_url}static/notebook",
            fullThemesUrl=f"{base_url}lab/api/themes",
            fullTranslationsApiUrl=f"{base_url}lab/api/translations",
            fullTreeUrl=f"{base_url}lab/tree",
            fullWorkspacesApiUrl=f"{base_url}lab/api/workspaces",
            labextensionsPath=[(lab.prefix_dir / "share" / "jupyter" / "labextensions").as_posix()],
            labextensionsUrl="/lab/extensions",
            licensesUrl="/lab/api/licenses",
            listingsUrl="/lab/api/listings",
            mathjaxConfig="TeX-AMS-MML_HTMLorMML-full,Safe",
            notebookLogo=False,
            notebookPage=notebook_page,
            schemasDir=(lab.prefix_dir / "share" / "jupyter" / "lab" / "schemas").as_posix(),
            settingsUrl="/lab/api/settings",
            staticDir=(notebook_dir / "static").as_posix(),
            templatesDir=(notebook_dir / "templates").as_posix(),
            terminalsAvailable=True,
            themesDir=(lab.prefix_dir / "share" / "jupyter" / "lab" / "themes").as_posix(),
            themesUrl="/lab/api/themes",
            translationsApiUrl="/lab/api/translations",
            treeUrl="/lab/tree",
            workspacesApiUrl="/lab/api/workspaces",
            wsUrl="",
        )
        _page_config = await self.page_config.get()
        index = (
            INDEX_HTML.replace("PAGE_CONFIG", json.dumps(_page_config))
            .replace("MAIN_ID", main_id)
            .replace("DOC_NAME", doc_name)
            .replace("BASE_URL", base_url)
            .replace("FULL_STATIC_URL", _page_config["fullStaticUrl"])
        )
        return index


INDEX_HTML = """\
<!doctype html>
<html>
    <head>
        <meta charset="utf-8"/>
        <meta name="viewport" content="width=device-width,initial-scale=1"/>
        <title>Home</title>
        <link rel="icon" type="image/x-icon" href="/static/favicons/favicon.ico" class="favicon"/>
        <link rel="stylesheet" href="/custom/custom.css"/>
        <script defer="defer" src="FULL_STATIC_URL/main.MAIN_ID.js?v=MAIN_ID"></script>
    </head>
    <body class="jp-ThemedContainer">
        <script id="jupyter-config-data" type="application/json">
            PAGE_CONFIG
        </script>
        <script>
            /* Remove token from URL. */
            (function() {
                var parsedUrl = new URL(window.location.href);
                if (parsedUrl.searchParams.get('token')) {
                    parsedUrl.searchParams.delete('token');
                    window.history.replaceState({}, '', parsedUrl.href);
                }
            }
            )();
        </script>
    </body>
</html>
"""
