import json
import logging
import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
from anyio import create_task_group, sleep, sleep_forever
from fps import get_root_module, merge_config
from fps_kernels.kernel_server.server import KernelServer, kernels
from httpx import AsyncClient
from httpx_ws import aconnect_ws
from httpx_ws.transport import ASGIWebSocketTransport
from jupyverse_api.kernel import Kernel

os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "config": {
            "start_server": False,
        },
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
            "page_config": {
                "type": "page_config",
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
            "file_watcher": {
                "type": "file_watcher",
            },
        },
    }
}


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_kernel_messages(auth_mode, capfd):
    kernel_id = "kernel_id_0"
    kernel_name = "python3"
    kernelspec_path = (
        Path(sys.prefix) / "share" / "jupyter" / "kernels" / kernel_name / "kernel.json"
    )
    assert kernelspec_path.exists()
    msg = {
        "channel": "shell",
        "parent_header": None,
        "content": None,
        "metadata": None,
        "header": {
            "msg_type": "msg_type_0",
            "msg_id": "0",
        },
    }

    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
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
    async with root_module as root_module:
        app = root_module.app
        transport = ASGIWebSocketTransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            kernel_server = KernelServer(
                kernelspec_path=kernelspec_path,
                capture_kernel_output=False,
                default_kernel_factory=KernelFactory(),
            )
            async with create_task_group() as tg:
                await tg.start(kernel_server.start)
                kernels[kernel_id] = {"server": kernel_server, "driver": None}

                # block msg_type_0
                kernel_server.block_messages("msg_type_0")
                async with aconnect_ws(
                    f"http://testserver/api/kernels/{kernel_id}/channels?session_id=session_id_0",
                    client,
                ) as websocket:
                    await websocket.send_json(msg)
                await sleep(0.1)
                out, err = capfd.readouterr()
                assert not err

                # allow only msg_type_0
                kernel_server.allow_messages("msg_type_0")
                async with aconnect_ws(
                    f"http://testserver/api/kernels/{kernel_id}/channels?session_id=session_id_0",
                    client,
                ) as websocket:
                    await websocket.send_json(msg)
                    await sleep(0.1)
                out, err = capfd.readouterr()
                assert err.count("msg_type_0") == 1

                # block all messages
                kernel_server.allow_messages([])
                async with aconnect_ws(
                    f"http://testserver/api/kernels/{kernel_id}/channels?session_id=session_id_0",
                    client,
                ) as websocket:
                    await websocket.send_json(msg)
                await sleep(0.1)
                out, err = capfd.readouterr()
                assert not err

                # allow all messages
                kernel_server.allow_messages()
                async with aconnect_ws(
                    f"http://testserver/api/kernels/{kernel_id}/channels?session_id=session_id_0",
                    client,
                ) as websocket:
                    await websocket.send_json(msg)
                await sleep(0.1)
                out, err = capfd.readouterr()
                assert err.count("msg_type_0") >= 1

                await kernel_server.stop()


@pytest.mark.anyio
async def test_wait_for_kernelspec(tmp_path, caplog):
    kernel_name = "python-wait-test"
    kernelspec_dir = tmp_path / kernel_name
    kernelspec_json = kernelspec_dir / "kernel.json"

    config = merge_config(
        CONFIG,
        {
            "jupyverse": {
                "modules": {
                    "auth": {"config": {"mode": "noauth"}},
                    "kernels": {"config": {"wait_for_kernelspec": True}},
                }
            }
        },
    )

    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    with patch("fps_kernels.kernel_driver.kernelspec.kernelspec_dirs", return_value=[tmp_path]):
        async with root_module as root_module:
            app = root_module.app
            transport = ASGIWebSocketTransport(app=app)
            kernelspec_dir.mkdir(parents=True)

            async def create_kernelspec_later():
                await sleep(0.2)
                kernel_spec = {
                    "argv": ["python", "-m", "ipykernel_launcher", "-f", "{connection_file}"],
                    "display_name": "Python 3",
                    "language": "python",
                }
                kernelspec_json.write_text(json.dumps(kernel_spec))

            async with create_task_group() as tg:
                tg.start_soon(create_kernelspec_later)
                async with AsyncClient(
                    transport=transport,
                    base_url="http://testserver",
                ) as client:
                    response = await client.post(
                        "/api/sessions",
                        json={
                            "kernel": {"name": kernel_name},
                            "name": "test",
                            "path": "test.ipynb",
                            "type": "notebook",
                        },
                    )

            assert response.status_code == 201
            with caplog.at_level(logging.INFO):
                assert (
                    len(
                        [
                            record
                            for record in caplog.records
                            if "Waiting for kernelspec" in record.message
                        ]
                    )
                    >= 1
                )
                assert any(kernel_name in record.message for record in caplog.records)


class KernelFactory:
    def __call__(self, *args, **kwargs) -> Kernel:
        return FakeKernel()


class FakeKernel(Kernel):
    async def start(self, *, task_status) -> None:
        async with (
            self._to_shell_send_stream,
            self._to_shell_receive_stream,
            self._from_shell_send_stream,
            self._from_shell_receive_stream,
            self._to_control_send_stream,
            self._to_control_receive_stream,
            self._from_control_send_stream,
            self._from_control_receive_stream,
            self._to_stdin_send_stream,
            self._to_stdin_receive_stream,
            self._from_stdin_send_stream,
            self._from_stdin_receive_stream,
            self._from_iopub_send_stream,
            self._from_iopub_receive_stream,
            create_task_group() as self.task_group,
        ):
            self.task_group.start_soon(self._run)
            task_status.started()
            await sleep_forever()

    async def _run(self):
        async with self._to_shell_receive_stream:
            async for msg in self._to_shell_receive_stream:
                print(msg, file=sys.stderr)

    async def stop(self) -> None:
        self.task_group.cancel_scope.cancel()

    async def interrupt(self) -> None:
        pass
