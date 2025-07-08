import pytest
from fps import get_root_module, merge_config
from httpx import AsyncClient
from httpx_ws import WebSocketUpgradeError, aconnect_ws
from utils import authenticate_client

from jupyverse_api.auth import AuthConfig

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
            "file_id": {
                "type": "file_id",
            },
            "frontend": {
                "type": "frontend",
            },
            "lab": {
                "type": "lab",
            },
            "jupyterlab": {
                "type": "jupyterlab",
            },
            "kernel_subprocess": {
                "type": "kernel_subprocess",
            },
            "kernels": {
                "type": "kernels",
            },
            "yjs": {
                "type": "yjs",
            },
        },
    }
}


@pytest.mark.anyio
async def test_kernel_channels_unauthenticated(unused_tcp_port):
    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": unused_tcp_port}}})
    async with get_root_module(config):
        with pytest.raises(WebSocketUpgradeError):
            async with aconnect_ws(
                f"http://127.0.0.1:{unused_tcp_port}/api/kernels/kernel_id_0/channels?session_id=session_id_0",
            ):
                pass


@pytest.mark.anyio
async def test_kernel_channels_authenticated(unused_tcp_port):
    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": unused_tcp_port}}})
    async with get_root_module(config), AsyncClient() as http:
        await authenticate_client(http, unused_tcp_port)
        async with aconnect_ws(
            f"http://127.0.0.1:{unused_tcp_port}/api/kernels/kernel_id_0/channels?session_id=session_id_0",
            http,
        ):
            pass


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth", "token", "user"))
async def test_root_auth(auth_mode, unused_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": unused_tcp_port},
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
    async with get_root_module(config), AsyncClient() as http:
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/")
        if auth_mode == "noauth":
            expected = 302
        elif auth_mode in ["token", "user"]:
            expected = 403

        assert response.status_code == expected
        assert response.headers["content-type"] == "application/json"


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_no_auth(auth_mode, unused_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": unused_tcp_port},
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
    async with get_root_module(config), AsyncClient() as http:
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/lab")
        assert response.status_code == 200


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("token",))
async def test_token_auth(auth_mode, unused_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": unused_tcp_port},
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
    async with get_root_module(config) as jupyverse, AsyncClient() as http:
        auth_config = await jupyverse.get(AuthConfig)

        # no token provided, should not work
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/")
        assert response.status_code == 403
        # token provided, should work
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/?token={auth_config.token}")
        assert response.status_code == 302


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("user",))
@pytest.mark.parametrize(
    "permissions",
    (
        {},
        {"admin": ["read"], "foo": ["bar", "baz"]},
    ),
)
async def test_permissions(auth_mode, permissions, unused_tcp_port):
    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "config": {"port": unused_tcp_port},
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
    async with get_root_module(config), AsyncClient() as http:
        await authenticate_client(http, unused_tcp_port, permissions=permissions)
        response = await http.get(f"http://127.0.0.1:{unused_tcp_port}/auth/user/me")
        if "admin" in permissions.keys():
            # we have the permissions
            assert response.status_code == 200
        else:
            # we don't have the permissions
            assert response.status_code == 403
