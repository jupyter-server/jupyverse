import asyncio
import json
from functools import partial
from pathlib import Path

import pytest
import requests
from fps_yjs.ydocs import ydocs
from fps_yjs.ywebsocket import WebsocketProvider
from pycrdt import Array, Doc, Map, Text
from websockets import connect

prev_theme = {}
test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_put(start_jupyverse):
    url = start_jupyverse
    # get previous theme
    response = requests.get(url + "/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    prev_theme["raw"] = json.loads(response.content)["raw"]
    # put new theme
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes", data=json.dumps(test_theme)
    )
    assert response.status_code == 204


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_get(start_jupyverse):
    url = start_jupyverse
    # get new theme
    response = requests.get(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
    )
    assert response.status_code == 200
    assert json.loads(response.content)["raw"] == test_theme["raw"]
    # put previous theme back
    response = requests.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        data=json.dumps(prev_theme),
    )
    assert response.status_code == 204


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
async def test_rest_api(start_jupyverse):
    url = start_jupyverse
    ws_url = url.replace("http", "ws", 1)
    name = "notebook0.ipynb"
    path = (Path("tests") / "data" / name).as_posix()
    # create a session to launch a kernel
    response = requests.post(
        f"{url}/api/sessions",
        data=json.dumps(
            {
                "kernel": {"name": "python3"},
                "name": name,
                "path": path,
                "type": "notebook",
            }
        ),
    )
    r = response.json()
    kernel_id = r["kernel"]["id"]
    # get the room ID for the document
    response = requests.put(
        f"{url}/api/collaboration/session/{path}",
        data=json.dumps(
            {
                "format": "json",
                "type": "notebook",
            }
        ),
    )
    file_id = response.json()["fileId"]
    document_id = f"json:notebook:{file_id}"
    ydoc = Doc()
    async with connect(
        f"{ws_url}/api/collaboration/room/{document_id}"
    ) as websocket, WebsocketProvider(ydoc, websocket):
        # connect to the shared notebook document
        # wait for file to be loaded and Y model to be created in server and client
        await asyncio.sleep(0.5)
        ydoc["cells"] = ycells = Array()
        # execute notebook
        for cell_idx in range(3):
            response = requests.post(
                f"{url}/api/kernels/{kernel_id}/execute",
                data=json.dumps(
                    {
                        "document_id": document_id,
                        "cell_id": ycells[cell_idx]["id"],
                    }
                ),
            )
        # wait for Y model to be updated
        await asyncio.sleep(0.5)
        # retrieve cells
        cells = json.loads(str(ycells))
        assert cells[0]["outputs"] == [
            {
                "data": {"text/plain": ["3"]},
                "execution_count": 1.0,
                "metadata": {},
                "output_type": "execute_result",
            }
        ]
        assert cells[1]["outputs"] == [
            {"name": "stdout", "output_type": "stream", "text": ["Hello World!\n"]}
        ]
        assert cells[2]["outputs"] == [
            {
                "data": {"text/plain": ["7"]},
                "execution_count": 3.0,
                "metadata": {},
                "output_type": "execute_result",
            }
        ]


@pytest.mark.asyncio
@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
async def test_ywidgets(start_jupyverse):
    url = start_jupyverse
    ws_url = url.replace("http", "ws", 1)
    name = "notebook1.ipynb"
    path = (Path("tests") / "data" / name).as_posix()
    # create a session to launch a kernel
    response = requests.post(
        f"{url}/api/sessions",
        data=json.dumps(
            {
                "kernel": {"name": "python3"},
                #"kernel": {"name": "akernel"},
                "name": name,
                "path": path,
                "type": "notebook",
            }
        ),
    )
    r = response.json()
    kernel_id = r["kernel"]["id"]
    # get the room ID for the document
    response = requests.put(
        f"{url}/api/collaboration/session/{path}",
        data=json.dumps(
            {
                "format": "json",
                "type": "notebook",
            }
        ),
    )
    file_id = response.json()["fileId"]
    document_id = f"json:notebook:{file_id}"
    ynb = ydocs["notebook"]()
    def callback(aevent, events, event):
        events.append(event)
        aevent.set()
    aevent = asyncio.Event()
    events = []
    ynb.ydoc.observe_subdocs(partial(callback, aevent, events))
    async with connect(
        f"{ws_url}/api/collaboration/room/{document_id}"
    ) as websocket, WebsocketProvider(ynb.ydoc, websocket):
        # connect to the shared notebook document
        # wait for file to be loaded and Y model to be created in server and client
        await asyncio.sleep(0.5)
        # execute notebook
        for cell_idx in range(2):
            response = requests.post(
                f"{url}/api/kernels/{kernel_id}/execute",
                data=json.dumps(
                    {
                        "document_id": document_id,
                        "cell_id": ynb.ycells[cell_idx]["id"],
                    }
                ),
            )
        while True:
            await aevent.wait()
            aevent.clear()
            guid = None
            for event in events:
                if event.added:
                    guid = event.added[0]
            if guid is not None:
                break
        task = asyncio.create_task(connect_ywidget(ws_url, guid))
        response = requests.post(
            f"{url}/api/kernels/{kernel_id}/execute",
            data=json.dumps(
                {
                    "document_id": document_id,
                    "cell_id": ynb.ycells[2]["id"],
                }
            ),
        )
        await task


async def connect_ywidget(ws_url, guid):
    ywidget_doc = Doc()
    async with connect(
        f"{ws_url}/api/collaboration/room/ywidget:{guid}"
    ) as websocket, WebsocketProvider(ywidget_doc, websocket):
        await asyncio.sleep(0.5)
        attrs = Map()
        model_name = Text()
        ywidget_doc["_attrs"] = attrs
        ywidget_doc["_model_name"] = model_name
        assert str(model_name) == "Switch"
        assert str(attrs) == '{"value":true}'
