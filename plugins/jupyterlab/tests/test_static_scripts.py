import pytest
from fps_jupyterlab.routes import _render_static_scripts


def test_render_static_scripts_preserves_order_and_base_url(tmp_path):
    runtime_name = "runtime.6f594760706896ab.js"
    main_name = "main.30eed593f68996dd7fc7.js"
    for asset_name in (runtime_name, main_name, "main.0a8b453df61deb67f669.js"):
        (tmp_path / asset_name).touch()
    (tmp_path / "index.html").write_text(
        f'<script defer src="{{{{page_config.fullStaticUrl}}}}/{runtime_name}"></script>'
        f'<script defer="defer" src="{{{{page_config.fullStaticUrl}}}}/'
        f'{main_name}?v=30eed593f68996dd7fc7"></script>',
        encoding="utf-8",
    )

    scripts = _render_static_scripts(tmp_path, "/jupyter/user/alice/static/lab/")

    assert scripts.splitlines() == [
        f'<script defer src="/jupyter/user/alice/static/lab/{runtime_name}"></script>',
        f'<script defer="defer" src="/jupyter/user/alice/static/lab/'
        f'{main_name}?v=30eed593f68996dd7fc7"></script>',
    ]
    assert "0a8b453df61deb67f669" not in scripts


@pytest.mark.parametrize("main_id", ("30eed593f68996dd7fc7", "0316a111134899af"))
def test_render_static_scripts_preserves_hash_formats(tmp_path, main_id):
    asset_name = f"main.{main_id}.js"
    (tmp_path / asset_name).touch()
    (tmp_path / "index.html").write_text(
        f'<script src="{{{{page_config.fullStaticUrl}}}}/{asset_name}?v={main_id}"></script>',
        encoding="utf-8",
    )

    scripts = _render_static_scripts(tmp_path, "/static/lab")

    assert scripts == f'<script src="/static/lab/{asset_name}?v={main_id}"></script>'


def test_render_static_scripts_rejects_missing_asset(tmp_path):
    (tmp_path / "index.html").write_text(
        '<script defer src="{{page_config.fullStaticUrl}}/main.missing.js"></script>',
        encoding="utf-8",
    )

    with pytest.raises(FileNotFoundError, match=r"main\.missing\.js"):
        _render_static_scripts(tmp_path, "/static/lab")


def test_render_static_scripts_requires_main_entrypoint(tmp_path):
    (tmp_path / "runtime.current.js").touch()
    (tmp_path / "index.html").write_text(
        '<script src="{{page_config.fullStaticUrl}}/runtime.current.js"></script>',
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="no main entry point"):
        _render_static_scripts(tmp_path, "/static/lab")
