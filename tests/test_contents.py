import base64
import os
from pathlib import Path

import pytest
from fps import get_root_module, merge_config
from httpx2 import AsyncClient
from utils import clear_content_values, create_content, sort_content_by_name

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "modules": {
            "app": {
                "type": "app",
            },
            "auth": {
                "type": "auth",
                "config": {
                    "test": True,
                },
            },
            "contents": {
                "type": "contents",
            },
            "frontend": {
                "type": "frontend",
            },
        },
    }
}


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_tree(auth_mode, tmp_path, free_tcp_port):
    prev_dir = os.getcwd()
    os.chdir(tmp_path)
    dname = Path(".")
    expected = []
    # write some files with different size
    for size in range(7, 13):
        fname = f"file_size_{size}"
        with (dname / fname).open("w") as f:
            f.write("-" * size)
        expected.append(
            create_content(
                content=None,
                type="file",
                size=size,
                mimetype="text/plain",
                name=fname,
                path=(dname / fname).as_posix(),
                format=None,
            )
        )
    # write some directories
    for i in range(3):
        sub_dname = f"directory_{i}"
        (dname / sub_dname).mkdir()
        expected.append(
            create_content(
                content=None,
                type="directory",
                size=None,
                mimetype=None,
                name=sub_dname,
                path=(dname / sub_dname).as_posix(),
                format="json",
            )
        )
    expected = create_content(
        content=expected,
        type="directory",
        size=None,
        mimetype=None,
        name="",
        path=dname.as_posix(),
        format="json",
    )

    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": free_tcp_port},
                "modules": {
                    "auth": {
                        "config": {
                            "mode": auth_mode,
                        }
                    }
                },
            }
        },
    )
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with root_module, AsyncClient() as http:
        response = await http.get(
            f"http://127.0.0.1:{free_tcp_port}/api/contents", params={"content": 1}
        )
        actual = response.json()
        # ignore modification and creation times
        clear_content_values(actual, keys=["created", "last_modified"])
        # ensure content names are ordered the same way
        sort_content_by_name(actual)
        sort_content_by_name(expected)
        assert actual == expected
        os.chdir(prev_dir)


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_get_file_format(auth_mode, tmp_path, free_tcp_port):
    prev_dir = os.getcwd()
    os.chdir(tmp_path)
    png = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
    Path("image.png").write_bytes(png)
    Path("data.csv").write_bytes(b"a,b\n1,2\n")
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": free_tcp_port},
                "modules": {
                    "auth": {
                        "config": {
                            "mode": auth_mode,
                        }
                    }
                },
            }
        },
    )
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    async with root_module, AsyncClient() as http:
        url = f"http://127.0.0.1:{free_tcp_port}/api/contents"
        # what JupyterLab requests to open an image
        response = await http.get(
            f"{url}/image.png", params={"type": "file", "format": "base64", "content": 1}
        )
        assert response.status_code == 200
        model = response.json()
        assert model["format"] == "base64"
        assert model["mimetype"] == "image/png"
        assert base64.b64decode(model["content"]) == png
        response = await http.get(
            f"{url}/data.csv", params={"type": "file", "format": "text", "content": 1}
        )
        model = response.json()
        assert model["format"] == "text"
        assert model["mimetype"] == "text/csv"
        assert model["content"] == "a,b\n1,2\n"
        # without a format, a file that is not UTF-8 is returned as base64
        response = await http.get(f"{url}/image.png", params={"content": 1})
        model = response.json()
        assert model["format"] == "base64"
        assert base64.b64decode(model["content"]) == png
    os.chdir(prev_dir)
