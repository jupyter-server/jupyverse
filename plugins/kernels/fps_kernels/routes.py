import json
import pathlib
import sys
import uuid
from http import HTTPStatus

from fps.hooks import register_router  # type: ignore
from fastapi import APIRouter, WebSocket, Response, Depends, status
from fastapi.responses import FileResponse
from starlette.requests import Request  # type: ignore

from fps_auth.backends import get_jwt_strategy, current_user  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_auth.db import get_user_db  # type: ignore
from fps_auth.config import get_auth_config  # type: ignore
from fps_lab.config import get_lab_config  # type: ignore

from .kernel_server.server import KernelServer, kernels  # type: ignore
from .models import Session

router = APIRouter()

kernelspecs: dict = {}
sessions: dict = {}
prefix_dir: pathlib.Path = pathlib.Path(sys.prefix)


@router.on_event("shutdown")
async def stop_kernels():
    for kernel in kernels.values():
        await kernel["server"].stop()


@router.get("/api/kernelspecs")
async def get_kernelspecs(
    lab_config=Depends(get_lab_config), user: User = Depends(current_user)
):
    for path in (prefix_dir / "share" / "jupyter" / "kernels").glob("*/kernel.json"):
        with open(path) as f:
            spec = json.load(f)
        name = path.parent.name
        resources = {
            f.stem: f"{lab_config.base_url}kernelspecs/{name}/{f.name}"
            for f in path.parent.iterdir()
            if f.is_file() and f.name != "kernel.json"
        }
        kernelspecs[name] = {"name": name, "spec": spec, "resources": resources}
    return {"default": "python3", "kernelspecs": kernelspecs}


@router.get("/kernelspecs/{kernel_name}/{file_name}")
async def get_kernelspec(
    kernel_name,
    file_name,
    user: User = Depends(current_user),
):
    return FileResponse(
        prefix_dir / "share" / "jupyter" / "kernels" / kernel_name / file_name
    )


@router.get("/api/kernels")
async def get_kernels(user: User = Depends(current_user)):
    results = []
    for kernel_id, kernel in kernels.items():
        results.append(
            {
                "id": kernel_id,
                "name": kernel["name"],
                "connections": kernel["server"].connections,
                "last_activity": kernel["server"].last_activity["date"],
                "execution_state": kernel["server"].last_activity["execution_state"],
            }
        )
    return results


@router.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: User = Depends(current_user),
):
    kernel_id = sessions[session_id]["kernel"]["id"]
    kernel_server = kernels[kernel_id]["server"]
    await kernel_server.stop()
    del kernels[kernel_id]
    del sessions[session_id]
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.patch("/api/sessions/{session_id}")
async def rename_session(
    request: Request,
    user: User = Depends(current_user),
):
    rename_session = await request.json()
    session_id = rename_session.pop("id")
    for key, value in rename_session.items():
        sessions[session_id][key] = value
    return Session(**sessions[session_id])


@router.get("/api/sessions")
async def get_sessions(user: User = Depends(current_user)):
    for session in sessions.values():
        kernel_id = session["kernel"]["id"]
        kernel_server = kernels[kernel_id]["server"]
        session["kernel"]["last_activity"] = kernel_server.last_activity["date"]
        session["kernel"]["execution_state"] = kernel_server.last_activity[
            "execution_state"
        ]
    return list(sessions.values())


@router.post(
    "/api/sessions",
    status_code=201,
    response_model=Session,
)
async def create_session(
    request: Request,
    user: User = Depends(current_user),
):
    create_session = await request.json()
    kernel_name = create_session["kernel"]["name"]
    kernel_server = KernelServer(
        kernelspec_path=str(
            prefix_dir / "share" / "jupyter" / "kernels" / kernel_name / "kernel.json"
        ),
    )
    kernel_id = str(uuid.uuid4())
    kernels[kernel_id] = {"name": kernel_name, "server": kernel_server}
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
            "connections": kernel_server.connections,
            "last_activity": kernel_server.last_activity["date"],
            "execution_state": kernel_server.last_activity["execution_state"],
        },
        "notebook": {"path": create_session["path"], "name": create_session["name"]},
    }
    sessions[session_id] = session
    return Session(**session)


@router.post("/api/kernels/{kernel_id}/restart")
async def restart_kernel(
    kernel_id,
    user: User = Depends(current_user),
):
    if kernel_id in kernels:
        kernel = kernels[kernel_id]
        await kernel["server"].restart()
        result = {
            "id": kernel_id,
            "name": kernel["name"],
            "connections": kernel["server"].connections,
            "last_activity": kernel["server"].last_activity["date"],
            "execution_state": kernel["server"].last_activity["execution_state"],
        }
        return result


@router.get("/api/kernels/{kernel_id}")
async def get_kernel(
    kernel_id,
    user: User = Depends(current_user),
):
    if kernel_id in kernels:
        kernel = kernels[kernel_id]
        result = {
            "id": kernel_id,
            "name": kernel["name"],
            "connections": kernel["server"].connections,
            "last_activity": kernel["server"].last_activity["date"],
            "execution_state": kernel["server"].last_activity["execution_state"],
        }
        return result


@router.websocket("/api/kernels/{kernel_id}/channels")
async def kernel_channels(
    websocket: WebSocket,
    kernel_id,
    session_id,
    auth_config=Depends(get_auth_config),
    user_db=Depends(get_user_db),
):
    accept_websocket = False
    if auth_config.mode == "noauth":
        accept_websocket = True
    else:
        cookie = websocket._cookies["fastapiusersauth"]
        user = await get_jwt_strategy().read_token(cookie, user_db)
        if user:
            accept_websocket = True
    if accept_websocket:
        await websocket.accept()
        if kernel_id in kernels:
            kernel_server = kernels[kernel_id]["server"]
            await kernel_server.serve(websocket, session_id)
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


r = register_router(router)
