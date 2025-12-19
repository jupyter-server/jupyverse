import pytest
from jupyverse_api.lab import PageConfig

pytestmark = pytest.mark.anyio


async def test_page_config():
    page_config = PageConfig()

    async def hook(config):
        config["foo"] += " baz"

    page_config.register(hook)
    page_config.set(foo="bar")
    config = await page_config.get()
    assert config == {"foo": "bar baz"}
