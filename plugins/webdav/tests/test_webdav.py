import sys
from pathlib import Path
from uuid import uuid4

import easywebdav  # type: ignore
import pytest
from anyio import to_thread
from fps import get_root_module, merge_config

CONFIG = {
    "jupyverse": {
        "type": "jupyverse_api.main:JupyverseModule",
        "modules": {
            "app": {
                "type": "jupyverse_api.main:AppModule",
            },
            "webdav": {
                "type": "webdav",
            },
        },
    }
}


@pytest.mark.anyio
@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python >=3.10")
async def test_webdav(unused_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {
                    "port": unused_tcp_port,
                },
                "modules": {
                    "webdav": {
                        "config": {
                            "account_mapping": [{"username": "foo", "password": "bar"}],
                        }
                    }
                },
            }
        },
    )
    async with get_root_module(config):
        webdav = easywebdav.connect(
            "127.0.0.1", port=unused_tcp_port, path="webdav", username="foo", password="bar"
        )
        dirname = str(uuid4())
        assert not Path(dirname).exists()
        await to_thread.run_sync(webdav.mkdir, dirname)
        assert Path(dirname).is_dir()
        await to_thread.run_sync(webdav.rmdir, dirname)
        assert not Path(dirname).exists()
