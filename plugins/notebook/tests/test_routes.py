from types import SimpleNamespace

import pytest
from fps_notebook.routes import _Notebook
from jupyverse_lab import PageConfig

pytestmark = pytest.mark.anyio


async def test_get_index_uses_template_entrypoint(tmp_path):
    notebook_dir = tmp_path / "notebook"
    static_dir = notebook_dir / "static"
    templates_dir = notebook_dir / "templates"
    static_dir.mkdir(parents=True)
    templates_dir.mkdir()
    (static_dir / "main.stale.js").touch()
    (static_dir / "main.current.js").touch()
    (templates_dir / "tree.html").write_text(
        '<script defer="defer" src="{{page_config.fullStaticUrl}}/'
        'main.current.js?v=current"></script>',
        encoding="utf-8",
    )
    notebook = object.__new__(_Notebook)
    notebook.page_config = PageConfig()

    index = await notebook.get_index(
        SimpleNamespace(prefix_dir=tmp_path),
        notebook_dir,
        [],
        [],
        "Tree",
        "tree",
        False,
        "/jupyter/user/alice/",
    )

    assert "/jupyter/user/alice/static/notebook/main.current.js?v=current" in index
    assert "main.stale.js" not in index
