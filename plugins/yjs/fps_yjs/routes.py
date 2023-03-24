import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple
from uuid import uuid4

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Request,
    Response,
    WebSocketDisconnect,
    status,
)
from jupyter_ydoc import ydocs as YDOCS  # type: ignore
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.contents import Contents
from jupyverse_api.yjs import Yjs
from ypy_websocket.websocket_server import WebsocketServer, YRoom
from ypy_websocket.ystore import BaseYStore, SQLiteYStore, YDocNotFound
from ypy_websocket.yutils import YMessageType, YSyncMessageType

from .models import CreateDocumentSession

YFILE = YDOCS["file"]
AWARENESS = 1
RENAME_SESSION = 127
SERVER_SESSION = uuid4().hex


class JupyterSQLiteYStore(SQLiteYStore):
    db_path = ".jupyter_ystore.db"


class _Yjs(Yjs):
    def __init__(
        self,
        app: App,
        auth: Auth,
        contents: Contents,
    ) -> None:
        super().__init__(app)

        class YDocWebSocketHandler:
            saving_document: Optional[asyncio.Task]
            websocket_server = JupyterWebsocketServer(rooms_ready=False, auto_clean_rooms=False)

            def __init__(self, websocket, path, permissions):
                self.websocket = websocket
                self.can_write = permissions is None or "write" in permissions.get("yjs", [])
                self.lock = asyncio.Lock()
                self.room = self.websocket_server.get_room(self.websocket.path)
                self.set_file_info(path)

            async def get_file_info(self) -> Tuple[str, str, str]:
                room_name = self.websocket_server.get_room_name(self.room)
                file_format, file_type, file_id = room_name.split(":", 2)
                file_path = await contents.file_id_manager.get_path(file_id)
                if file_path is None:
                    raise RuntimeError(f"File {self.room.document.path} cannot be found anymore")
                if file_path != self.room.document.path:
                    self.room.document.path = file_path
                return file_format, file_type, file_path

            def set_file_info(self, value: str) -> None:
                self.websocket_server.rename_room(value, from_room=self.room)
                self.websocket.path = value

            async def serve(self):
                self.set_file_info(self.websocket.path)
                self.saving_document = None
                self.room.on_message = self.on_message

                # cancel the deletion of the room if it was scheduled
                if not self.room.is_transient and self.room.cleaner is not None:
                    self.room.cleaner.cancel()

                if not self.room.is_transient and not self.room.ready:
                    file_format, file_type, file_path = await self.get_file_info()
                    is_notebook = file_type == "notebook"
                    model = await contents.read_content(file_path, True, as_json=is_notebook)
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
                            # if YStore updates and source file are out-of-sync, resync updates
                            # with source
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
                if not self.room.is_transient and not self.room.clients:
                    # no client in this room after we disconnect
                    # keep the document for a while in case someone reconnects
                    self.room.cleaner = asyncio.create_task(self.clean_room())

            async def on_message(self, message: bytes) -> bool:
                """
                Called whenever a message is received, before forwarding it to other clients.

                :param message: received message
                :returns: True if the message must be discarded, False otherwise (default: False).
                """
                skip = False
                byte = message[0]
                msg = message[1:]
                if byte == RENAME_SESSION:
                    # The client moved the document to a different location. After receiving this
                    # message, we make the current document available under a different url.
                    # The other clients are automatically notified of this change because
                    # the path is shared through the Yjs document as well.
                    new_room_name = msg.decode("utf-8")
                    self.set_file_info(new_room_name)
                    self.websocket_server.rename_room(new_room_name, from_room=self.room)
                    # send rename acknowledge
                    await self.websocket.send(bytes([RENAME_SESSION, 1]))
                elif byte == AWARENESS:
                    # changes = self.room.awareness.get_changes(msg)
                    # # filter out message depending on changes
                    # skip = True
                    pass
                elif byte == YMessageType.SYNC:
                    if not self.can_write and msg[0] == YSyncMessageType.SYNC_UPDATE:
                        skip = True
                else:
                    skip = True
                return skip

            async def watch_file(self):
                file_format, file_type, file_path = await self.get_file_info()
                while True:
                    watcher = contents.file_id_manager.watch(file_path)
                    async for changes in watcher:
                        file_format, file_type, new_file_path = await self.get_file_info()
                        if new_file_path != file_path:
                            # file was renamed
                            contents.file_id_manager.unwatch(file_path, watcher)
                            file_path = new_file_path
                            break
                        await self.maybe_load_document()

            async def maybe_load_document(self):
                file_format, file_type, file_path = await self.get_file_info()
                async with self.lock:
                    model = await contents.read_content(file_path, False)
                # do nothing if the file was saved by us
                if self.last_modified < to_datetime(model.last_modified):
                    is_notebook = file_type == "notebook"
                    model = await contents.read_content(file_path, True, as_json=is_notebook)
                    self.room.document.source = model.content
                    self.last_modified = to_datetime(model.last_modified)

            async def clean_room(self) -> None:
                await asyncio.sleep(60)  # FIXME: pass in config
                if self.room.watcher:
                    self.room.watcher.cancel()
                self.room.document.unobserve()
                self.websocket_server.delete_room(room=self.room)

            def on_document_change(self, target, event):
                if target == "state" and "dirty" in event.keys:
                    dirty = event.keys["dirty"]["newValue"]
                    if not dirty:
                        # we cleared the dirty flag, nothing to save
                        return
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
                    file_format, file_type, file_path = await self.get_file_info()
                except Exception:
                    return
                is_notebook = file_type == "notebook"
                async with self.lock:
                    model = await contents.read_content(file_path, True, as_json=is_notebook)
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
                    async with self.lock:
                        await contents.write_content(content)
                        model = await contents.read_content(file_path, False)
                        self.last_modified = to_datetime(model.last_modified)
                self.room.document.dirty = False

        router = APIRouter()

        async def serve_room(websocket_permissions, path):
            if websocket_permissions is None:
                return
            websocket, permissions = websocket_permissions
            await websocket.accept()
            socket = YDocWebSocketHandler(WebsocketAdapter(websocket, path), path, permissions)
            await socket.serve()

        @router.websocket("/api/yjs/{path:path}")
        async def yjs_websocket(
            path,
            websocket_permissions=Depends(
                auth.websocket_auth(permissions={"yjs": ["read", "write"]})
            ),
        ):
            await serve_room(websocket_permissions, path)

        @router.websocket("/api/collaboration/room/{path:path}")
        async def collaboration_room_websocket(
            path,
            websocket_permissions=Depends(
                auth.websocket_auth(permissions={"yjs": ["read", "write"]})
            ),
        ):
            await serve_room(websocket_permissions, path)

        @router.put("/api/collaboration/session/{path:path}", status_code=200)
        async def create_roomid(
            path,
            request: Request,
            response: Response,
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ):
            # we need to process the request manually
            # see https://github.com/tiangolo/fastapi/issues/3373#issuecomment-1306003451
            create_document_session = CreateDocumentSession(**(await request.json()))
            idx = await contents.file_id_manager.get_id(path)
            if idx is not None:
                return {
                    "format": create_document_session.format,
                    "type": create_document_session.type,
                    "fileId": idx,
                    "sessionId": SERVER_SESSION,
                }

            idx = await contents.file_id_manager.index(path)
            if idx is None:
                raise HTTPException(status_code=404, detail=f"File {path} does not exist")

            response.status_code = status.HTTP_201_CREATED
            return {
                "format": create_document_session.format,
                "type": create_document_session.type,
                "fileId": idx,
                "sessionId": SERVER_SESSION,
            }

        self.include_router(router)

        self.YDocWebSocketHandler = YDocWebSocketHandler


def to_datetime(iso_date: str) -> datetime:
    return datetime.fromisoformat(iso_date.rstrip("Z"))


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


class DocumentRoom(YRoom):
    """A Y room for a possibly stored document (e.g. a notebook)."""

    is_transient = False

    def __init__(self, type: str, ystore: BaseYStore):
        super().__init__(ready=False, ystore=ystore)
        self.type = type
        self.cleaner = None
        self.watcher = None
        self.document = YDOCS.get(type, YFILE)(self.ydoc)


class TransientRoom(YRoom):
    """A Y room for sharing state (e.g. awareness)."""

    is_transient = True


class JupyterWebsocketServer(WebsocketServer):
    def get_room(self, path: str) -> YRoom:
        if path not in self.rooms.keys():
            if path.count(":") >= 2:
                # it is a stored document (e.g. a notebook)
                file_format, file_type, file_path = path.split(":", 2)
                p = Path(file_path)
                updates_file_path = (p.parent / f".{file_type}:{p.name}.y").as_posix()
                ystore = JupyterSQLiteYStore(path=updates_file_path)  # FIXME: pass in config
                self.rooms[path] = DocumentRoom(file_type, ystore)
            else:
                # it is a transient document (e.g. awareness)
                self.rooms[path] = TransientRoom()
        return self.rooms[path]
