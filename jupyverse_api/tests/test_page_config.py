import pytest
from fps import Context, Module, get, put
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


async def test_context_in_hook():
    value = None

    async def get_page_config(page_config):
        await page_config.get()

    async def hook(config):
        nonlocal value
        with await get(str) as value:
            pass

    class MyModule(Module):
        async def prepare(self):
            self.page_config = await self.get(PageConfig)
            self.page_config.register(hook)

        async def start(self):
            async with Context():
                put("foo")
                await get_page_config(self.page_config)

    class RootModule(Module):
        def __init__(self):
            super().__init__("root")
            self.add_module("jupyverse_api.lab:PageConfigModule", "page_config")
            self.add_module(MyModule, "my_module")

    async with RootModule():
        pass

    assert value == "foo"
