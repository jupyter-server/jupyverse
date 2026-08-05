import pytest
from jupyverse_lab import parse_static_scripts


def test_parse_static_scripts():
    scripts = parse_static_scripts(
        '<script defer src="/static/runtime.js"></script>'
        '<script src="/static/main.js?v=current#entry"></script>'
    )

    assert [script.path.name for script in scripts] == ["runtime.js", "main.js"]
    assert scripts[0].attributes == (("defer", None), ("src", "/static/runtime.js"))
    assert scripts[1].query == "v=current"
    assert scripts[1].fragment == "entry"


@pytest.mark.parametrize(
    "source",
    (
        "https://example.com/main.js",
        "//example.com/main.js",
        "../main.js",
        r"..\main.js",
    ),
)
def test_parse_static_scripts_rejects_non_local_sources(source):
    with pytest.raises(ValueError, match="not local"):
        parse_static_scripts(f'<script src="{source}"></script>')
