import json
import logging
import uuid
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from fastapi import HTTPException, Response
from fastapi.responses import FileResponse
from starlette.requests import Request
from watchfiles import Change, awatch
from jupyverse_api.auth import Auth, User
from jupyverse_api.kernels import Kernels, KernelsConfig
from jupyverse_api.kernels.models import CreateSession, Execution, Kernel, Notebook, Session
from jupyverse_api.frontend import FrontendConfig
from jupyverse_api.yjs import Yjs
from jupyverse_api.app import App

from .kernel_driver.driver import KernelDriver
from .kernel_driver.kernelspec import find_kernelspec, kernelspec_dirs
from .kernel_server.server import (
    AcceptedWebSocket,
    KernelServer,
    kernels,
)


logger = logging.getLogger("kernels")


class _Kernels(Kernels):
    def __init__(
        self,
        app: App,
        kernels_config: KernelsConfig,
        auth: Auth,
        frontend_config: FrontendConfig,
        yjs: Optional[Yjs],
    ) -> None:
        super().__init__(app=app, auth=auth)
        self.kernels_config = kernels_config
        self.frontend_config = frontend_config
        self.yjs = yjs

        self.kernelspecs: dict = {}
        self.kernel_id_to_connection_file: Dict[str, str] = {}
        self.sessions: Dict[str, Session] = {}
        self.kernels = kernels

    async def get_kernelspecs(
        self,
        user: User,
    ):
        for search_path in kernelspec_dirs():
            for path in Path(search_path).glob("*/kernel.json"):
                with open(path) as f:
                    spec = json.load(f)
                name = path.parent.name
                resources = {
                    f.stem: f"{self.frontend_config.base_url}kernelspecs/{name}/{f.name}"
                    for f in path.parent.iterdir()
                    if f.is_file() and f.name != "kernel.json"
                }
                self.kernelspecs[name] = {"name": name, "spec": spec, "resources": resources}
        return {"default": self.kernels_config.default_kernel, "kernelspecs": self.kernelspecs}

    async def get_kernelspec(
        self,
        kernel_name,
        file_name,
        user: User,
    ):
        for search_path in kernelspec_dirs():
            file_path = Path(search_path) / kernel_name / file_name
            if file_path.exists():
                return FileResponse(file_path)

        raise HTTPException(
            status_code=404, detail=f"Kernelspec {kernel_name}/{file_name} not found"
        )

    async def get_kernels(
        self,
        user: User,
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

    async def delete_session(
        self,
        session_id: str,
        user: User,
    ):
        kernel_id = self.sessions[session_id].kernel.id
        kernel_server = kernels[kernel_id]["server"]
        await kernel_server.stop()
        del kernels[kernel_id]
        if kernel_id in self.kernel_id_to_connection_file:
            del self.kernel_id_to_connection_file[kernel_id]
        del self.sessions[session_id]
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def rename_session(
        self,
        request: Request,
        user: User,
    ):
        rename_session = await request.json()
        session_id = rename_session.pop("id")
        for key, value in rename_session.items():
            setattr(self.sessions[session_id], key, value)
        return self.sessions[session_id]

    async def get_sessions(
        self,
        user: User,
    ):
        for session in self.sessions.values():
            kernel_id = session.kernel.id
            kernel_server = kernels[kernel_id]["server"]
            session.kernel.last_activity = kernel_server.last_activity["date"]
            session.kernel.execution_state = kernel_server.last_activity["execution_state"]
        return list(self.sessions.values())

    async def create_session(
        self,
        request: Request,
        user: User,
    ):
        create_session = CreateSession(**(await request.json()))
        kernel_id = create_session.kernel.id
        kernel_name = create_session.kernel.name
        if kernel_name is not None:
            # launch a new ("internal") kernel
            kernel_cwd = Path(create_session.path).parent
            while True:
                if kernel_cwd.is_dir():
                    break
                kernel_cwd = kernel_cwd.parent
            kernel_server = KernelServer(
                kernelspec_path=Path(find_kernelspec(kernel_name)).as_posix(),
                kernel_cwd=str(kernel_cwd),
            )
            kernel_id = str(uuid.uuid4())
            kernels[kernel_id] = {"name": kernel_name, "server": kernel_server, "driver": None}
            await kernel_server.start()
        elif kernel_id is not None:
            # external kernel
            kernel_name = kernels[kernel_id]["name"]
            kernel_server = KernelServer(
                connection_file=self.kernel_id_to_connection_file[kernel_id],
                write_connection_file=False,
            )
            kernels[kernel_id]["server"] = kernel_server
            await kernel_server.start(launch_kernel=False)
        else:
            return
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            path=create_session.path,
            name=create_session.name,
            type=create_session.type,
            kernel=Kernel(
                id=kernel_id,
                name=kernel_name,
                connections=kernel_server.connections,
                last_activity=kernel_server.last_activity["date"],
                execution_state=kernel_server.last_activity["execution_state"],
            ),
            notebook=Notebook(
                path=create_session.path,
                name=create_session.name,
            ),
        )
        self.sessions[session_id] = session
        return session

    async def interrupt_kernel(
        self,
        kernel_id,
        user: User,
    ):
        if kernel_id in kernels:
            kernel = kernels[kernel_id]
            kernel["server"].interrupt()
            result = {
                "id": kernel_id,
                "name": kernel["name"],
                "connections": kernel["server"].connections,
                "last_activity": kernel["server"].last_activity["date"],
                "execution_state": kernel["server"].last_activity["execution_state"],
            }
            return result

    async def restart_kernel(
        self,
        kernel_id,
        user: User,
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

    async def execute_cell(
        self,
        request: Request,
        kernel_id,
        user: User,
    ):
        if self.yjs is None:
            raise RuntimeError("Cannot execute without a Yjs plugin.")

        r = await request.json()
        execution = Execution(**r)
        if kernel_id in kernels:
            ynotebook = self.yjs.get_document(execution.document_id)
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

    async def get_kernel(
        self,
        kernel_id,
        user: User,
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

    async def shutdown_kernel(
        self,
        kernel_id,
        user: User,
    ):
        if kernel_id in kernels:
            await kernels[kernel_id]["server"].stop()
            del kernels[kernel_id]
        for session_id in [k for k, v in self.sessions.items() if v.kernel.id == kernel_id]:
            del self.sessions[session_id]
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def kernel_channels(
        self,
        kernel_id,
        session_id,
        websocket_permissions,
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

    async def watch_connection_files(self, path: Path) -> None:
        # first time scan, treat everything as added files
        initial_changes = {(Change.added, str(p)) for p in path.iterdir()}
        await self.process_connection_files(initial_changes)
        # then, on every change
        async for changes in awatch(path):
            await self.process_connection_files(changes)

    async def process_connection_files(self, changes: Set[Tuple[Change, str]]):
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
                        kernel_id = list(self.kernel_id_to_connection_file.keys())[
                            list(self.kernel_id_to_connection_file.values()).index(path)
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
                    self.kernel_id_to_connection_file[kernel_id] = path
                    kernels[kernel_id] = {
                        "name": data["kernel_name"],
                        "server": None,
                        "driver": None,
                    }
