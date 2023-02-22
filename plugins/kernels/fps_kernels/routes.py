import asyncio
import json
import sys
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Set, Tuple

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.responses import FileResponse
from fps.hooks import register_router  # type: ignore
from fps_auth_base import User, current_user, websocket_auth  # type: ignore
from fps_frontend.config import get_frontend_config  # type: ignore
from fps_yjs.routes import YDocWebSocketHandler  # type: ignore
from starlette.requests import Request  # type: ignore
from watchfiles import Change, awatch

from .config import get_kernel_config
from .kernel_driver.driver import KernelDriver  # type: ignore
from .kernel_driver.kernelspec import find_kernelspec, kernelspec_dirs
from .kernel_server.server import (  # type: ignore
    AcceptedWebSocket,
    KernelServer,
    kernels,
)
from .models import CreateSession, Execution, Session

router = APIRouter()

kernelspecs: dict = {}
kernel_id_to_connection_file: Dict[str, str] = {}
sessions: dict = {}
prefix_dir: Path = Path(sys.prefix)


async def process_connection_files(changes: Set[Tuple[Change, str]]):
    # get rid of "simultaneously" added/deleted files
    file_changes: Dict[str, List[Change]] = {}
    for c in changes:
        change, path = c
        if path not in file_changes:
            file_changes[path] = []
        file_changes[path].append(change)
    to_delete: List[str] = []
    for p, cs in file_changes.items():
        if Change.added in cs and Change.deleted in cs:
            cs.remove(Change.added)
            cs.remove(Change.deleted)
            if not cs:
                to_delete.append(p)
    for p in to_delete:
        del file_changes[p]
    # process file changes
    for path, cs in file_changes.items():
        for change in cs:
            if change == Change.deleted:
                if path in kernels:
                    kernel_id = list(kernel_id_to_connection_file.keys())[
                        list(kernel_id_to_connection_file.values()).index(path)
                    ]
                    del kernels[kernel_id]
            elif change == Change.added:
                try:
                    data = json.loads(Path(path).read_text())
                except BaseException:
                    continue
                if "kernel_name" not in data or "key" not in data:
                    continue
                # looks like a kernel connection file
                kernel_id = str(uuid.uuid4())
                kernel_id_to_connection_file[kernel_id] = path
                kernels[kernel_id] = {"name": data["kernel_name"], "server": None, "driver": None}


async def watch_connection_files(path: Path):
    # first time scan, treat everything as added files
    initial_changes = {(Change.added, str(p)) for p in path.iterdir()}
    await process_connection_files(initial_changes)
    # then, on every change
    async for changes in awatch(path):
        await process_connection_files(changes)


@router.on_event("startup")
async def startup():
    kernel_config = get_kernel_config()
    if kernel_config.connection_path is not None:
        path = Path(kernel_config.connection_path)
        asyncio.create_task(watch_connection_files(path))


@router.on_event("shutdown")
async def stop_kernels():
    for kernel in kernels.values():
        await kernel["server"].stop()


@router.get("/api/kernelspecs")
async def get_kernelspecs(
    frontend_config=Depends(get_frontend_config),
    kernel_config=Depends(get_kernel_config),
    user: User = Depends(current_user(permissions={"kernelspecs": ["read"]})),
):
    for search_path in kernelspec_dirs():
        for path in Path(search_path).glob("*/kernel.json"):
            with open(path) as f:
                spec = json.load(f)
            name = path.parent.name
            resources = {
                f.stem: f"{frontend_config.base_url}kernelspecs/{name}/{f.name}"
                for f in path.parent.iterdir()
                if f.is_file() and f.name != "kernel.json"
            }
            kernelspecs[name] = {"name": name, "spec": spec, "resources": resources}
    return {"default": kernel_config.default_kernel, "kernelspecs": kernelspecs}


@router.get("/kernelspecs/{kernel_name}/{file_name}")
async def get_kernelspec(
    kernel_name,
    file_name,
    user: User = Depends(current_user()),
):
    for search_path in kernelspec_dirs():
        file_path = Path(search_path) / kernel_name / file_name
        if file_path.exists():
            return FileResponse(file_path)
    raise HTTPException(status_code=404, detail=f"Kernelspec {kernel_name}/{file_name} not found")


@router.get("/api/kernels")
async def get_kernels(
    user: User = Depends(current_user(permissions={"kernels": ["read"]})),
):
    results = []
    for kernel_id, kernel in kernels.items():
        if kernel["server"]:
            connections = kernel["server"].connections
            last_activity = kernel["server"].last_activity["date"]
            execution_state = kernel["server"].last_activity["execution_state"]
        else:
            connections = 0
            last_activity = ""
            execution_state = "idle"
        results.append(
            {
                "id": kernel_id,
                "name": kernel["name"],
                "connections": connections,
                "last_activity": last_activity,
                "execution_state": execution_state,
            }
        )
    return results


@router.delete("/api/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    user: User = Depends(current_user(permissions={"sessions": ["write"]})),
):
    kernel_id = sessions[session_id]["kernel"]["id"]
    kernel_server = kernels[kernel_id]["server"]
    await kernel_server.stop()
    del kernels[kernel_id]
    if kernel_id in kernel_id_to_connection_file:
        del kernel_id_to_connection_file[kernel_id]
    del sessions[session_id]
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.patch("/api/sessions/{session_id}")
async def rename_session(
    request: Request,
    user: User = Depends(current_user(permissions={"sessions": ["write"]})),
):
    rename_session = await request.json()
    session_id = rename_session.pop("id")
    for key, value in rename_session.items():
        sessions[session_id][key] = value
    return Session(**sessions[session_id])


@router.get("/api/sessions")
async def get_sessions(
    user: User = Depends(current_user(permissions={"sessions": ["read"]})),
):
    for session in sessions.values():
        kernel_id = session["kernel"]["id"]
        kernel_server = kernels[kernel_id]["server"]
        session["kernel"]["last_activity"] = kernel_server.last_activity["date"]
        session["kernel"]["execution_state"] = kernel_server.last_activity["execution_state"]
    return list(sessions.values())


@router.post(
    "/api/sessions",
    status_code=201,
    response_model=Session,
)
async def create_session(
    request: Request,
    user: User = Depends(current_user(permissions={"sessions": ["write"]})),
):
    create_session = CreateSession(**(await request.json()))
    kernel_id = create_session.kernel.id
    kernel_name = create_session.kernel.name
    if kernel_name is not None:
        # launch a new ("internal") kernel
        kernel_server = KernelServer(
            kernelspec_path=Path(find_kernelspec(kernel_name)).as_posix(),
            kernel_cwd=str(Path(create_session.path).parent),
        )
        kernel_id = str(uuid.uuid4())
        kernels[kernel_id] = {"name": kernel_name, "server": kernel_server, "driver": None}
        await kernel_server.start()
    elif kernel_id is not None:
        # external kernel
        kernel_name = kernels[kernel_id]["name"]
        kernel_server = KernelServer(
            connection_file=kernel_id_to_connection_file[kernel_id],
            write_connection_file=False,
        )
        kernels[kernel_id]["server"] = kernel_server
        await kernel_server.start(launch_kernel=False)
    else:
        return
    session_id = str(uuid.uuid4())
    session = {
        "id": session_id,
        "path": create_session.path,
        "name": create_session.name,
        "type": create_session.type,
        "kernel": {
            "id": kernel_id,
            "name": kernel_name,
            "connections": kernel_server.connections,
            "last_activity": kernel_server.last_activity["date"],
            "execution_state": kernel_server.last_activity["execution_state"],
        },
        "notebook": {"path": create_session.path, "name": create_session.name},
    }
    sessions[session_id] = session
    return Session(**session)


@router.post("/api/kernels/{kernel_id}/restart")
async def restart_kernel(
    kernel_id,
    user: User = Depends(current_user(permissions={"kernels": ["write"]})),
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


@router.post("/api/kernels/{kernel_id}/execute")
async def execute_cell(
    request: Request,
    kernel_id,
    user: User = Depends(current_user(permissions={"kernels": ["write"]})),
):
    r = await request.json()
    execution = Execution(**r)
    if kernel_id in kernels:
        ynotebook = YDocWebSocketHandler.websocket_server.get_room(execution.document_id).document
        cell = ynotebook.get_cell(execution.cell_idx)
        cell["outputs"] = []

        kernel = kernels[kernel_id]
        if not kernel["driver"]:
            kernel["driver"] = driver = KernelDriver(
                kernelspec_path=Path(find_kernelspec(kernel["name"])).as_posix(),
                write_connection_file=False,
                connection_file=kernel["server"].connection_file_path,
            )
            await driver.connect()
        driver = kernel["driver"]

        await driver.execute(cell)
        ynotebook.set_cell(execution.cell_idx, cell)


@router.get("/api/kernels/{kernel_id}")
async def get_kernel(
    kernel_id,
    user: User = Depends(current_user(permissions={"kernels": ["read"]})),
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
    kernel_id,
    session_id,
    websocket_permissions=Depends(websocket_auth(permissions={"kernels": ["execute"]})),
):
    if websocket_permissions is None:
        return
    websocket, permissions = websocket_permissions
    subprotocol = (
        "v1.kernel.websocket.jupyter.org"
        if "v1.kernel.websocket.jupyter.org" in websocket["subprotocols"]
        else None
    )
    await websocket.accept(subprotocol=subprotocol)
    accepted_websocket = AcceptedWebSocket(websocket, subprotocol)
    if kernel_id in kernels:
        kernel_server = kernels[kernel_id]["server"]
        if kernel_server is None:
            # this is an external kernel
            # kernel is already launched, just start a kernel server
            kernel_server = KernelServer(
                connection_file=kernel_id,
                write_connection_file=False,
            )
            await kernel_server.start(launch_kernel=False)
            kernels[kernel_id]["server"] = kernel_server
        await kernel_server.serve(accepted_websocket, session_id, permissions)


r = register_router(router)
