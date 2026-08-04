from pathlib import Path
from types import SimpleNamespace

import pytest
from fps_jupyterlab.routes import _JupyterLab
from jupyverse_lab import PageConfig

pytestmark = pytest.mark.anyio


def build_jupyterlab(static_lab_dir, prefix_dir):
    jupyterlab = object.__new__(_JupyterLab)
    jupyterlab.static_lab_dir = static_lab_dir
    jupyterlab._jupyterlab_module = SimpleNamespace(__version__="test")
    jupyterlab.page_config = PageConfig()
    jupyterlab.lab = SimpleNamespace(prefix_dir=prefix_dir)
    jupyterlab.disabled_extensions = []
    jupyterlab.federated_extensions = []
    return jupyterlab


async def test_get_index_uses_manifest_entrypoints(tmp_path, monkeypatch):
    static_lab_dir = tmp_path / "static"
    static_lab_dir.mkdir()
    main_stale = static_lab_dir / "main.stale.js"
    main_current = static_lab_dir / "main.current.js"
    vendor_stale = static_lab_dir / "vendors-node_modules_whatwg-fetch_fetch_js.stale.js"
    vendor_current = static_lab_dir / "vendors-node_modules_whatwg-fetch_fetch_js.current.js"
    for path in (main_stale, main_current, vendor_stale, vendor_current):
        path.touch()
    (static_lab_dir / "index.html").write_text(
        '<script defer src="{{page_config.fullStaticUrl}}/'
        'vendors-node_modules_whatwg-fetch_fetch_js.current.js"></script>'
        '<script defer src="{{page_config.fullStaticUrl}}/main.current.js?v=current"></script>',
        encoding="utf-8",
    )

    original_glob = Path.glob

    def stale_first(path, pattern):
        if path == static_lab_dir and pattern == "main.*.js":
            return iter((main_stale, main_current))
        if path == static_lab_dir:
            return iter((vendor_stale, vendor_current))
        return original_glob(path, pattern)

    monkeypatch.setattr(Path, "glob", stale_first)
    jupyterlab = build_jupyterlab(static_lab_dir, tmp_path)

    index = await jupyterlab.get_index("default", False, False, False)

    assert "/static/lab/main.current.js?v=current" in index
    assert "/static/lab/vendors-node_modules_whatwg-fetch_fetch_js.current.js" in index
    assert "stale.js" not in index


async def test_get_index_ignores_orphan_vendor_entrypoint(tmp_path):
    static_lab_dir = tmp_path / "static"
    static_lab_dir.mkdir()
    (static_lab_dir / "main.current.js").touch()
    (static_lab_dir / "vendors-node_modules_whatwg-fetch_fetch_js.stale.js").touch()
    (static_lab_dir / "index.html").write_text(
        '<script defer src="{{page_config.fullStaticUrl}}/main.current.js?v=current"></script>',
        encoding="utf-8",
    )
    jupyterlab = build_jupyterlab(static_lab_dir, tmp_path)

    index = await jupyterlab.get_index("default", False, False, False)

    assert "/static/lab/main.current.js?v=current" in index
    assert "vendors-node_modules_whatwg-fetch_fetch_js" not in index
