import sys
from copy import deepcopy
from pathlib import Path
from uuid import uuid4

import easywebdav  # type: ignore
import pytest
from anyio import to_thread
from asphalt.core import Context
from jupyverse_api.main import JupyverseComponent


COMPONENTS = {
    "app": {"type": "app"},
    "webdav": {"type": "webdav"},
}


def configure(components, config):
    _components = deepcopy(components)
    for k1, v1 in config.items():
        for k2, v2 in v1.items():
            _components[k1][k2] = v2
    return _components


@pytest.mark.asyncio
@pytest.mark.skipif(sys.version_info < (3, 10), reason="Requires Python >=3.10")
async def test_webdav(unused_tcp_port):
    components = configure(
        COMPONENTS, {"webdav": {"account_mapping": [{"username": "foo", "password": "bar"}]}}
    )
    async with Context() as ctx:
        await JupyverseComponent(
            components=components,
            port=unused_tcp_port,
        ).start(ctx)

        webdav = easywebdav.connect(
            "127.0.0.1", port=unused_tcp_port, path="webdav", username="foo", password="bar"
        )
        dirname = str(uuid4())
        assert not Path(dirname).exists()
        await to_thread.run_sync(webdav.mkdir, dirname)
        assert Path(dirname).is_dir()
        await to_thread.run_sync(webdav.rmdir, dirname)
        assert not Path(dirname).exists()
