import asyncio
import re
from datetime import datetime
from pathlib import Path
from typing import Optional, Set, Tuple

import fastapi
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, status
from fps.hooks import register_router  # type: ignore
from fps_auth.backends import (  # type: ignore
    UserManager,
    get_jwt_strategy,
    get_user_manager,
)
from fps_auth.config import get_auth_config  # type: ignore
from fps_contents.routes import read_content, write_content  # type: ignore
from jupyter_ydoc import ydocs as YDOCS  # type: ignore
from ypy_websocket.websocket_server import WebsocketServer, YRoom  # type: ignore
from ypy_websocket.ystore import BaseYStore, SQLiteYStore, YDocNotFound  # type: ignore

YFILE = YDOCS["file"]
RENAME_SESSION = 127


class JupyterSQLiteYStore(SQLiteYStore):
    db_path = ".jupyter_ystore.db"


router = APIRouter()


def get_path_param_names(path: str) -> Set[str]:
    return {name.split(":")[0] for name in re.findall("{(.*?)}", path)}


# FIXME: remove the patch when https://github.com/tiangolo/fastapi/pull/3879 is merged
fastapi.utils.get_path_param_names.__code__ = get_path_param_names.__code__


def to_datetime(iso_date: str) -> datetime:
    return datetime.fromisoformat(iso_date.rstrip("Z"))


@router.websocket("/api/yjs/{format}:{type}:{path:path}")
async def websocket_endpoint(
    websocket: WebSocket,
    format,
    type,
    path,
    auth_config=Depends(get_auth_config),
    user_manager: UserManager = Depends(get_user_manager),
):
    accept_websocket = False
    if auth_config.mode == "noauth":
        accept_websocket = True
    elif "fastapiusersauth" in websocket._cookies:
        token = websocket._cookies["fastapiusersauth"]
        user = await get_jwt_strategy().read_token(token, user_manager)
        if user:
            accept_websocket = True
    if accept_websocket:
        await websocket.accept()
        full_path = f"{format}:{type}:{path}"
        socket = YDocWebSocketHandler(WebsocketAdapter(websocket, full_path), full_path)
        await socket.serve()
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


class WebsocketAdapter:
    """An adapter to make a Starlette's WebSocket look like a ypy-websocket's WebSocket"""

    def __init__(self, websocket, path: str):
        self._websocket = websocket
        self._path = path

    @property
    def path(self) -> str:
        return self._path

    @path.setter
    def path(self, value: str) -> None:
        self._path = value

    def __aiter__(self):
        return self

    async def __anext__(self):
        try:
            message = await self._websocket.receive_bytes()
        except WebSocketDisconnect:
            raise StopAsyncIteration()
        return message

    async def send(self, message):
        await self._websocket.send_bytes(message)

    async def recv(self):
        return await self._websocket.receive_bytes()


class JupyterRoom(YRoom):
    def __init__(self, type: str, ystore: BaseYStore):
        super().__init__(ready=False, ystore=ystore)
        self.type = type
        self.cleaner = None
        self.watcher = None
        self.document = YDOCS.get(type, YFILE)(self.ydoc)


class JupyterWebsocketServer(WebsocketServer):
    def get_room(self, path: str) -> JupyterRoom:
        file_format, file_type, file_path = path.split(":", 2)
        if path not in self.rooms.keys():
            p = Path(file_path)
            updates_file_path = str(p.parent / f".{file_type}:{p.name}.y")
            ystore = JupyterSQLiteYStore(path=updates_file_path)  # FIXME: pass in config
            self.rooms[path] = JupyterRoom(file_type, ystore)
        return self.rooms[path]


class YDocWebSocketHandler:

    saving_document: Optional[asyncio.Task]
    websocket_server = JupyterWebsocketServer(rooms_ready=False, auto_clean_rooms=False)

    def __init__(self, websocket, path):
        self.websocket = websocket
        self.room = self.websocket_server.get_room(self.websocket.path)
        self.set_file_info(path)

    def get_file_info(self) -> Tuple[str, str, str]:
        room_name = self.websocket_server.get_room_name(self.room)
        file_format, file_type, file_path = room_name.split(":", 2)
        return file_format, file_type, file_path

    def set_file_info(self, value: str) -> None:
        self.websocket_server.rename_room(value, from_room=self.room)
        self.websocket.path = value

    async def serve(self):
        self.set_file_info(self.websocket.path)
        self.saving_document = None
        self.room.on_message = self.on_message

        # cancel the deletion of the room if it was scheduled
        if self.room.cleaner is not None:
            self.room.cleaner.cancel()

        if not self.room.ready:
            file_format, file_type, file_path = self.get_file_info()
            is_notebook = file_type == "notebook"
            model = await read_content(file_path, True, as_json=is_notebook)
            self.last_modified = to_datetime(model.last_modified)
            # check again if ready, because loading the file is async
            if not self.room.ready:
                # try to apply Y updates from the YStore for this document
                try:
                    await self.room.ystore.apply_updates(self.room.ydoc)
                    read_from_source = False
                except YDocNotFound:
                    # YDoc not found in the YStore, create the document from
                    # the source file (no change history)
                    read_from_source = True
                if not read_from_source:
                    # if YStore updates and source file are out-of-sync, resync updates with source
                    if self.room.document.source != model.content:
                        read_from_source = True
                if read_from_source:
                    self.room.document.source = model.content
                    await self.room.ystore.encode_state_as_update(self.room.ydoc)

                self.room.document.dirty = False
                self.room.ready = True
                self.room.watcher = asyncio.create_task(self.watch_file())
                # save the document when changed
                self.room.document.observe(self.on_document_change)

        await self.websocket_server.serve(self.websocket)
        if self.room.clients == [self.websocket]:
            # no client in this room after we disconnect
            # keep the document for a while in case someone reconnects
            self.room.cleaner = asyncio.create_task(self.clean_room())

    async def on_message(self, message):
        if message[0] == RENAME_SESSION:
            # The client moved the document to a different location. After receiving this message,
            # we make the current document available under a different url.
            # The other clients are automatically notified of this change because
            # the path is shared through the Yjs document as well.
            new_room_name = message[1:].decode("utf-8")
            self.set_file_info(new_room_name)
            self.websocket_server.rename_room(new_room_name, from_room=self.room)
            # send rename acknowledge
            await self.websocket.send(bytes([RENAME_SESSION, 1]))

    async def watch_file(self):
        poll_interval = 1  # FIXME: pass in config
        if not poll_interval:
            self.room.watcher = None
            return
        while True:
            await asyncio.sleep(poll_interval)
            await self.maybe_load_document()

    async def maybe_load_document(self):
        file_format, file_type, file_path = self.get_file_info()
        model = await read_content(file_path, False)
        # do nothing if the file was saved by us
        if self.last_modified < to_datetime(model.last_modified):
            is_notebook = file_type == "notebook"
            model = await read_content(file_path, True, as_json=is_notebook)
            self.room.document.source = model.content
            self.last_modified = to_datetime(model.last_modified)

    async def clean_room(self) -> None:
        await asyncio.sleep(60)  # FIXME: pass in config
        if self.room.watcher:
            self.room.watcher.cancel()
        self.room.document.unobserve()
        self.websocket_server.delete_room(room=self.room)

    def on_document_change(self, event):
        try:
            dirty = event.keys["dirty"]["newValue"]
            if not dirty:
                # we cleared the dirty flag, nothing to save
                return
        except Exception:
            pass
        # unobserve and observe again because the structure of the document may have changed
        # e.g. a new cell added to a notebook
        self.room.document.unobserve()
        self.room.document.observe(self.on_document_change)
        if self.saving_document is not None and not self.saving_document.done():
            # the document is being saved, cancel that
            self.saving_document.cancel()
            self.saving_document = None
        self.saving_document = asyncio.create_task(self.maybe_save_document())

    async def maybe_save_document(self):
        # save after 1 second of inactivity to prevent too frequent saving
        await asyncio.sleep(1)
        # if the room cannot be found, don't save
        try:
            file_format, file_type, file_path = self.get_file_info()
        except Exception:
            return
        is_notebook = file_type == "notebook"
        model = await read_content(file_path, True, as_json=is_notebook)
        if self.last_modified < to_datetime(model.last_modified):
            # file changed on disk, let's revert
            self.room.document.source = model.content
            self.last_modified = to_datetime(model.last_modified)
            return
        if model.content != self.room.document.source:
            # don't save if not needed
            # this also prevents the dirty flag from bouncing between windows of
            # the same document opened as different types (e.g. notebook/text editor)
            format = "json" if file_type == "notebook" else "text"
            content = {
                "content": self.room.document.source,
                "format": format,
                "path": file_path,
                "type": file_type,
            }
            await write_content(content)
            model = await read_content(file_path, False)
            self.last_modified = to_datetime(model.last_modified)
        self.room.document.dirty = False


r = register_router(router)
