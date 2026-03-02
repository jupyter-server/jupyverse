import json
from pathlib import Path

import anyio
import httpx
import pytest
from jupyter_ydoc import ydocs
from jupyverse_api.yrooms import AsyncWebSocketClient
from pycrdt import Array, Doc, Map, Text

prev_theme = {}
test_theme = {"raw": '{// jupyverse test\n"theme": "JupyterLab Dark"}'}


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_put(start_jupyverse):
    url = start_jupyverse
    # get previous theme
    response = httpx.get(url + "/lab/api/settings/@jupyterlab/apputils-extension:themes")
    assert response.status_code == 200
    prev_theme["raw"] = json.loads(response.content)["raw"]
    # put new theme
    response = httpx.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        content=json.dumps(test_theme),
    )
    assert response.status_code == 204


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_settings_persistence_get(start_jupyverse):
    url = start_jupyverse
    # get new theme
    response = httpx.get(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
    )
    assert response.status_code == 200
    assert json.loads(response.content)["raw"] == test_theme["raw"]
    # put previous theme back
    response = httpx.put(
        url + "/lab/api/settings/@jupyterlab/apputils-extension:themes",
        content=json.dumps(prev_theme),
    )
    assert response.status_code == 204


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
async def test_rest_api(start_jupyverse):
    url = start_jupyverse
    name = "notebook0.ipynb"
    path = (Path("data") / name).as_posix()
    # create a session to launch a kernel
    response = httpx.post(
        f"{url}/api/sessions",
        content=json.dumps(
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
    response = httpx.put(
        f"{url}/api/collaboration/session/{path}",
        content=json.dumps(
            {
                "format": "json",
                "type": "notebook",
            }
        ),
    )
    file_id = response.json()["fileId"]
    document_id = f"json:notebook:{file_id}"
    ydoc = Doc()
    ycells = ydoc.get("cells", type=Array)

    async with (
        ydoc.events() as events,
        AsyncWebSocketClient(id=f"api/collaboration/room/{document_id}", doc=ydoc, url=url),
    ):
        async for event in events:
            if len(ycells) == 3:
                break

        # execute notebook
        for cell_idx in range(3):
            response = httpx.post(
                f"{url}/api/kernels/{kernel_id}/execute",
                content=json.dumps(
                    {
                        "document_id": document_id,
                        "cell_id": ycells[cell_idx]["id"],
                    }
                ),
            )
        # wait for Y model to be updated
        # retrieve cells
        with anyio.fail_after(5):
            while True:
                await anyio.sleep(0.1)
                cells = json.loads(str(ycells))
                if (
                    cells[0]["outputs"]
                    == [
                        {
                            "data": {"text/plain": "3"},
                            "execution_count": 1,
                            "metadata": {},
                            "output_type": "execute_result",
                        }
                    ]
                    and cells[1]["outputs"]
                    == [{"name": "stdout", "output_type": "stream", "text": "Hello World!\n"}]
                    and cells[2]["outputs"]
                    == [
                        {
                            "data": {"text/plain": "7"},
                            "execution_count": 3,
                            "metadata": {},
                            "output_type": "execute_result",
                        }
                    ]
                ):
                    break


@pytest.mark.anyio
@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
async def test_ywidgets(start_jupyverse):
    url = start_jupyverse
    name = "notebook1.ipynb"
    path = (Path("data") / name).as_posix()
    # create a session to launch a kernel
    response = httpx.post(
        f"{url}/api/sessions",
        content=json.dumps(
            {
                "kernel": {"name": "python3"},
                # "kernel": {"name": "akernel"},
                "name": name,
                "path": path,
                "type": "notebook",
            }
        ),
    )
    r = response.json()
    kernel_id = r["kernel"]["id"]
    # get the room ID for the document
    response = httpx.put(
        f"{url}/api/collaboration/session/{path}",
        content=json.dumps(
            {
                "format": "json",
                "type": "notebook",
            }
        ),
    )
    file_id = response.json()["fileId"]
    document_id = f"json:notebook:{file_id}"
    ynb = ydocs["notebook"]()

    async with (
        ynb.ydoc.events(subdocs=True) as events,
        AsyncWebSocketClient(
            id=f"api/collaboration/room/{document_id}",
            doc=ynb.ydoc,
            url=url,
        ),
    ):
        # connect to the shared notebook document
        # wait for file to be loaded and Y model to be created in server and client
        await anyio.sleep(0.5)
        # execute notebook
        for cell_idx in range(2):
            response = httpx.post(
                f"{url}/api/kernels/{kernel_id}/execute",
                content=json.dumps(
                    {
                        "document_id": document_id,
                        "cell_id": ynb.ycells[cell_idx]["id"],
                    }
                ),
            )
        async for event in events:
            if event.added:
                guid = event.added[0]
                break

        async with anyio.create_task_group() as tg:
            tg.start_soon(connect_ywidget, url, guid)
            response = httpx.post(
                f"{url}/api/kernels/{kernel_id}/execute",
                content=json.dumps(
                    {
                        "document_id": document_id,
                        "cell_id": ynb.ycells[2]["id"],
                    }
                ),
            )


async def connect_ywidget(url, guid):
    ywidget_doc = Doc()
    async with AsyncWebSocketClient(
        id=f"api/collaboration/room/ywidget:{guid}",
        doc=ywidget_doc,
        url=url,
    ):
        attrs = ywidget_doc.get("_attrs", type=Map)
        model_name = ywidget_doc.get("_model_name", type=Text)
        with anyio.fail_after(5):
            while True:
                await anyio.sleep(0.1)
                if str(model_name) == "Switch" and str(attrs) == '{"value":true}':
                    break
