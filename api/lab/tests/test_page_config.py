import json
import sys
from pathlib import Path

import pytest
from fps import Context, Module, get, get_root_module, put
from jupyverse_lab import PageConfig

pytestmark = pytest.mark.anyio


async def test_page_config_basic():
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
            self.add_module("jupyverse_lab:PageConfigModule", "page_config")
            self.add_module(MyModule, "my_module")

    async with RootModule():
        pass

    assert value == "foo"


@pytest.fixture
def tmp_page_config():
    page_config_dir = Path(sys.prefix) / "etc" / "jupyter" / "labconfig"
    page_config_dir.mkdir(exist_ok=True)
    page_config_path = page_config_dir / "page_config.json"
    page_config_path.write_text(json.dumps({"terminalsAvailable": False}))
    yield
    page_config_path.unlink()


async def test_page_config_file(tmp_page_config):
    config = {
        "jupyverse": {
            "type": "jupyverse",
            "modules": {
                "app": {"type": "app"},
                "auth": {"type": "noauth"},
                "frontend": {"type": "frontend"},
                "page_config": {"type": "page_config"},
                "lab": {"type": "lab"},
                "jupyterlab": {"type": "jupyterlab"},
            },
        },
    }

    async with get_root_module(config) as module:
        page_config = await module.get(PageConfig)
        page_config_dict = await page_config.get()
        assert page_config_dict == {"terminalsAvailable": False}
