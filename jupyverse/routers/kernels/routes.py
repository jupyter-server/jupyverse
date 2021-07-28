import sys
import json
import uuid
import pathlib

from fastapi import WebSocket
from fastapi.responses import FileResponse
from starlette.requests import Request

from kernel_server import KernelServer  # type: ignore

from .models import Session

from jupyverse import JAPIRouter


def init(jupyverse):
    router.init(jupyverse)
    return router


class KernelRouter(JAPIRouter):
    def init(self, jupyverse):
        self.jupyverse = jupyverse
        self.kernelspecs = {}
        self.sessions = {}
        self.kernels = {}

        self.prefix_dir = pathlib.Path(sys.prefix)

        self.jupyverse.app.include_router(router)


router = KernelRouter()


@router.get("/api/kernelspecs")
async def get_kernelspecs():
    for path in (router.prefix_dir / "share" / "jupyter" / "kernels").glob(
        "*/kernel.json"
    ):
        with open(path) as f:
            spec = json.load(f)
        name = path.parent.name
        resources = {
            f.stem: f"/kernelspecs/{name}/{f.name}"
            for f in path.parent.iterdir()
            if f.is_file() and f.name != "kernel.json"
        }
        router.kernelspecs[name] = {"name": name, "spec": spec, "resources": resources}
    return {"default": "python3", "kernelspecs": router.kernelspecs}


@router.get("/kernelspecs/{kernel_name}/{file_name}")
async def get_kernelspec(kernel_name, file_name):
    return FileResponse(
        router.prefix_dir / "share" / "jupyter" / "kernels" / kernel_name / file_name
    )


@router.get("/api/kernels")
async def get_kernels():
    return [
        {
            "id": kernel_id,
            "name": v["name"],
            "last_activity": "2021-07-27T09:50:07.217545Z",
            "execution_state": "idle",
            "connections": 0,
        }
        for kernel_id, v in router.kernels.items()
    ]


@router.patch("/api/sessions/{session_id}")
async def get_session(request: Request):
    rename_session = await request.json()
    session_id = rename_session.pop("id")
    for key, value in rename_session.items():
        router.sessions[session_id][key] = value
    return Session(**router.sessions[session_id])


@router.get("/api/sessions")
async def get_sessions():
    return list(router.sessions.values())


@router.post(
    "/api/sessions",
    status_code=201,
    response_model=Session,
)
async def create_session(request: Request):
    create_session = await request.json()
    kernel_name = create_session["kernel"]["name"]
    kernel_server = KernelServer(
        kernelspec_path=str(
            router.prefix_dir
            / "share"
            / "jupyter"
            / "kernels"
            / kernel_name
            / "kernel.json"
        )
    )
    kernel_id = str(uuid.uuid4())
    router.kernels[kernel_id] = {"name": kernel_name, "server": kernel_server}
    await kernel_server.start()
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "path": create_session["path"],
        "name": create_session["name"],
        "type": create_session["type"],
        "kernel": {
            "id": kernel_id,
            "name": create_session["kernel"]["name"],
            "last_activity": "2021-07-23T15:01:36.393348Z",
            "execution_state": "starting",
            "connections": 0,
        },
        "notebook": {"path": create_session["path"], "name": create_session["name"]},
    }
    router.sessions[session_id] = session
    return Session(**session)


@router.websocket("/api/kernels/{kernel_id}/channels")
async def websocket_endpoint(websocket: WebSocket, kernel_id, session_id):
    await websocket.accept()
    kernel_server = router.kernels[kernel_id]["server"]
    await kernel_server.serve(websocket)
