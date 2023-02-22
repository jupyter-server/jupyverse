import os
import sys
from pathlib import Path
from time import sleep

import pytest
from fps_kernels.kernel_server.server import KernelServer, kernels

os.environ["PYDEVD_DISABLE_FILE_VALIDATION"] = "1"


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("noauth",))
async def test_kernel_messages(client, capfd):
    kernel_id = "kernel_id_0"
    kernel_name = "python3"
    kernelspec_path = (
        Path(sys.prefix) / "share" / "jupyter" / "kernels" / kernel_name / "kernel.json"
    )
    assert kernelspec_path.exists()
    kernel_server = KernelServer(kernelspec_path=kernelspec_path, capture_kernel_output=False)
    await kernel_server.start()
    kernels[kernel_id] = {"server": kernel_server}
    msg_id = "0"
    msg = {
        "channel": "shell",
        "parent_header": None,
        "content": None,
        "metadata": None,
        "header": {
            "msg_type": "msg_type_0",
            "msg_id": msg_id,
        },
    }

    # block msg_type_0
    msg["header"]["msg_id"] = str(int(msg["header"]["msg_id"]) + 1)
    kernel_server.block_messages("msg_type_0")
    with client.websocket_connect(
        f"/api/kernels/{kernel_id}/channels?session_id=session_id_0",
    ) as websocket:
        websocket.send_json(msg)
    sleep(0.5)
    out, err = capfd.readouterr()
    assert not err

    # allow only msg_type_0
    msg["header"]["msg_id"] = str(int(msg["header"]["msg_id"]) + 1)
    kernel_server.allow_messages("msg_type_0")
    with client.websocket_connect(
        f"/api/kernels/{kernel_id}/channels?session_id=session_id_0",
    ) as websocket:
        websocket.send_json(msg)
    sleep(0.5)
    out, err = capfd.readouterr()
    assert err.count("[IPKernelApp] WARNING | Unknown message type: 'msg_type_0'") == 1

    # block all messages
    msg["header"]["msg_id"] = str(int(msg["header"]["msg_id"]) + 1)
    kernel_server.allow_messages([])
    with client.websocket_connect(
        f"/api/kernels/{kernel_id}/channels?session_id=session_id_0",
    ) as websocket:
        websocket.send_json(msg)
    sleep(0.5)
    out, err = capfd.readouterr()
    assert not err

    # allow all messages
    msg["header"]["msg_id"] = str(int(msg["header"]["msg_id"]) + 1)
    kernel_server.allow_messages()
    with client.websocket_connect(
        f"/api/kernels/{kernel_id}/channels?session_id=session_id_0",
    ) as websocket:
        websocket.send_json(msg)
    sleep(0.5)
    out, err = capfd.readouterr()
    assert err.count("[IPKernelApp] WARNING | Unknown message type: 'msg_type_0'") == 1
