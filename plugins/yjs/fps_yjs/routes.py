from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from functools import partial
from typing import Dict
from uuid import uuid4

from fastapi import (
    HTTPException,
    Request,
    Response,
    WebSocketDisconnect,
    status,
)
from jupyter_ydoc import ydocs as YDOCS
from jupyter_ydoc.ybasedoc import YBaseDoc
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.contents import Contents
from jupyverse_api.yjs import Yjs
from jupyverse_api.yjs.models import CreateDocumentSession
from websockets.exceptions import ConnectionClosedOK
from ypy_websocket.websocket_server import WebsocketServer, YRoom
from ypy_websocket.ystore import SQLiteYStore, YDocNotFound
from ypy_websocket.yutils import YMessageType, YSyncMessageType

YFILE = YDOCS["file"]
AWARENESS = 1
SERVER_SESSION = uuid4().hex
logger = logging.getLogger("yjs")


class JupyterSQLiteYStore(SQLiteYStore):
    db_path = ".jupyter_ystore.db"  # FIXME: pass in config


class _Yjs(Yjs):
    def __init__(
        self,
        app: App,
        auth: Auth,
        contents: Contents,
    ) -> None:
        super().__init__(app=app, auth=auth)
        self.contents = contents
        self.room_manager = RoomManager(contents)

    async def collaboration_room_websocket(
        self,
        path,
        websocket_permissions,
    ):
        if websocket_permissions is None:
            return
        websocket, permissions = websocket_permissions
        await websocket.accept()
        ypy_websocket = YpyWebsocket(websocket, path)
        await self.room_manager.serve(ypy_websocket, permissions)

    async def create_roomid(
        self,
        path,
        request: Request,
        response: Response,
        user: User,
    ):
        # we need to process the request manually
        # see https://github.com/tiangolo/fastapi/issues/3373#issuecomment-1306003451
        create_document_session = CreateDocumentSession(**(await request.json()))
        idx = await self.contents.file_id_manager.get_id(path)
        res = {
            "format": create_document_session.format,
            "type": create_document_session.type,
            "sessionId": SERVER_SESSION,
        }
        if idx is not None:
            res["fileId"] = idx
            return res

        idx = await self.contents.file_id_manager.index(path)
        if idx is None:
            raise HTTPException(status_code=404, detail=f"File {path} does not exist")

        response.status_code = status.HTTP_201_CREATED
        res["fileId"] = idx
        return res

    def get_document(self, document_id: str) -> YBaseDoc:
        return self.room_manager.documents[document_id]


def to_datetime(iso_date: str) -> datetime:
    return datetime.fromisoformat(iso_date.rstrip("Z"))


class YpyWebsocket:
    """An wrapper to make a Starlette's WebSocket look like a ypy-websocket's WebSocket"""

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
        try:
            await self._websocket.send_bytes(message)
        except ConnectionClosedOK:
            return

    async def recv(self):
        return await self._websocket.receive_bytes()


class RoomManager:
    contents: Contents
    documents: Dict[str, YBaseDoc]
    watchers: Dict[str, asyncio.Task]
    savers: Dict[str, asyncio.Task]
    cleaners: Dict[YRoom, asyncio.Task]
    last_modified: Dict[str, datetime]
    websocket_server: JupyterWebsocketServer
    lock: asyncio.Lock

    def __init__(self, contents: Contents):
        self.contents = contents
        self.documents = {}  # a dictionary of room_name:document
        self.watchers = {}  # a dictionary of file_id:task
        self.savers = {}  # a dictionary of file_id:task
        self.cleaners = {}  # a dictionary of room:task
        self.last_modified = {}  # a dictionary of file_id:last_modification_date
        self.websocket_server = JupyterWebsocketServer(rooms_ready=False, auto_clean_rooms=False)
        self.websocket_server_task = asyncio.create_task(self.websocket_server.start())
        self.lock = asyncio.Lock()

    def stop(self):
        for watcher in self.watchers.values():
            watcher.cancel()
        for saver in self.savers.values():
            saver.cancel()
        for cleaner in self.cleaners.values():
            cleaner.cancel()
        self.websocket_server.stop()

    async def serve(self, websocket: YpyWebsocket, permissions) -> None:
        room = await self.websocket_server.get_room(websocket.path)
        can_write = permissions is None or "write" in permissions.get("yjs", [])
        room.on_message = partial(self.filter_message, can_write)
        is_stored_document = websocket.path.count(":") >= 2
        if is_stored_document:
            assert room.ystore is not None
            file_format, file_type, file_id = websocket.path.split(":", 2)
            if room in self.cleaners:
                # cleaning the room was scheduled because there was no client left
                # cancel that since there is a new client
                self.cleaners[room].cancel()
            if not room.ready:
                file_path = await self.contents.file_id_manager.get_path(file_id)
                logger.info(f"Opening collaboration room: {websocket.path} ({file_path})")
                document = YDOCS.get(file_type, YFILE)(room.ydoc)
                self.documents[websocket.path] = document
                async with self.lock:
                    model = await self.contents.read_content(file_path, True, file_format)
                assert model.last_modified is not None
                self.last_modified[file_id] = to_datetime(model.last_modified)
                if not room.ready:
                    # try to apply Y updates from the YStore for this document
                    try:
                        await room.ystore.apply_updates(room.ydoc)
                        read_from_source = False
                    except YDocNotFound:
                        # YDoc not found in the YStore, create the document from
                        # the source file (no change history)
                        read_from_source = True
                    if not read_from_source:
                        # if YStore updates and source file are out-of-sync, resync updates
                        # with source
                        if document.source != model.content:
                            read_from_source = True
                    if read_from_source:
                        document.source = model.content
                        await room.ystore.encode_state_as_update(room.ydoc)

                    document.dirty = False
                    room.ready = True
                    # save the document to file when changed
                    document.observe(
                        partial(self.on_document_change, file_id, file_type, file_format, document)
                    )
                    # update the document when file changes
                    if file_id not in self.watchers:
                        self.watchers[file_id] = asyncio.create_task(
                            self.watch_file(file_format, file_id, document)
                        )

        await self.websocket_server.started.wait()
        await self.websocket_server.serve(websocket)

        if is_stored_document and not room.clients:
            # no client in this room after we disconnect
            self.cleaners[room] = asyncio.create_task(self.maybe_clean_room(room, websocket.path))

    async def filter_message(self, can_write: bool, message: bytes) -> bool:
        """
        Called whenever a message is received, before forwarding it to other clients.

        :param can_write: True if updating the document is permitted, False otherwise.
        :param message: received message.
        :returns: True if the message must be discarded, False otherwise (default: False).
        """
        skip = False
        byte = message[0]
        msg = message[1:]
        if byte == AWARENESS:
            # changes = self.room.awareness.get_changes(msg)
            # # filter out message depending on changes
            # skip = True
            pass
        elif byte == YMessageType.SYNC:
            if not can_write and msg[0] == YSyncMessageType.SYNC_UPDATE:
                skip = True
        else:
            skip = True
        return skip

    async def get_file_path(self, file_id: str, document) -> str | None:
        file_path = await self.contents.file_id_manager.get_path(file_id)
        if file_path is None:
            return
        if file_path != document.path:
            document.path = file_path
        return file_path

    async def watch_file(self, file_format: str, file_id: str, document: YBaseDoc) -> None:
        file_path = await self.get_file_path(file_id, document)
        assert file_path is not None
        logger.debug(f"Watching file: {file_path}")
        while True:
            watcher = self.contents.file_id_manager.watch(file_path)
            async for changes in watcher:
                new_file_path = await self.get_file_path(file_id, document)
                if new_file_path is None:
                    continue
                if new_file_path != file_path:
                    # file was renamed
                    self.contents.file_id_manager.unwatch(file_path, watcher)
                    file_path = new_file_path
                    # break
                await self.maybe_load_file(file_format, file_path, file_id)

    async def maybe_load_file(self, file_format: str, file_path: str, file_id: str) -> None:
        async with self.lock:
            model = await self.contents.read_content(file_path, False)
        # do nothing if the file was saved by us
        assert model.last_modified is not None
        if self.last_modified[file_id] < to_datetime(model.last_modified):
            # the file was not saved by us, update the shared document(s)
            async with self.lock:
                model = await self.contents.read_content(file_path, True, file_format)
            assert model.last_modified is not None
            documents = [v for k, v in self.documents.items() if k.split(":", 2)[2] == file_id]
            for document in documents:
                document.source = model.content
            self.last_modified[file_id] = to_datetime(model.last_modified)

    def on_document_change(
        self, file_id: str, file_type: str, file_format: str, document: YBaseDoc, target, event
    ) -> None:
        if target == "state" and "dirty" in event.keys:
            dirty = event.keys["dirty"]["newValue"]
            if not dirty:
                # we cleared the dirty flag, nothing to save
                return
        # unobserve and observe again because the structure of the document may have changed
        # e.g. a new cell added to a notebook
        document.unobserve()
        document.observe(
            partial(self.on_document_change, file_id, file_type, file_format, document)
        )
        if file_id in self.savers:
            self.savers[file_id].cancel()
        self.savers[file_id] = asyncio.create_task(
            self.maybe_save_document(file_id, file_type, file_format, document)
        )

    async def maybe_save_document(
        self, file_id: str, file_type: str, file_format: str, document: YBaseDoc
    ) -> None:
        # save after 1 second of inactivity to prevent too frequent saving
        await asyncio.sleep(1)  # FIXME: pass in config
        # if the room cannot be found, don't save
        try:
            file_path = await self.get_file_path(file_id, document)
        except BaseException:
            return
        assert file_path is not None
        async with self.lock:
            model = await self.contents.read_content(file_path, True, file_format)
        assert model.last_modified is not None
        if self.last_modified[file_id] < to_datetime(model.last_modified):
            # file changed on disk, let's revert
            document.source = model.content
            self.last_modified[file_id] = to_datetime(model.last_modified)
            return
        if model.content != document.source:
            # don't save if not needed
            # this also prevents the dirty flag from bouncing between windows of
            # the same document opened as different types (e.g. notebook/text editor)
            content = {
                "content": document.source,
                "format": file_format,
                "path": file_path,
                "type": file_type,
            }
            async with self.lock:
                await self.contents.write_content(content)
                model = await self.contents.read_content(file_path, False)
            assert model.last_modified is not None
            self.last_modified[file_id] = to_datetime(model.last_modified)
        document.dirty = False
        # we're done saving, remove the saver
        del self.savers[file_id]

    async def maybe_clean_room(self, room, ws_path: str) -> None:
        file_id = ws_path.split(":", 2)[2]
        # keep the document for a while in case someone reconnects
        await asyncio.sleep(60)  # FIXME: pass in config
        document = self.documents[ws_path]
        document.unobserve()
        del self.documents[ws_path]
        documents = [v for k, v in self.documents.items() if k.split(":", 2)[2] == file_id]
        if not documents:
            self.watchers[file_id].cancel()
            del self.watchers[file_id]
        room_name = self.websocket_server.get_room_name(room)
        self.websocket_server.delete_room(room=room)
        file_path = await self.get_file_path(file_id, document)
        logger.info(f"Closing collaboration room: {room_name} ({file_path})")


class JupyterWebsocketServer(WebsocketServer):
    async def get_room(self, ws_path: str) -> YRoom:
        if ws_path not in self.rooms:
            if ws_path.count(":") >= 2:
                # it is a stored document (e.g. a notebook)
                file_format, file_type, file_id = ws_path.split(":", 2)
                updates_file_path = f".{file_type}:{file_id}.y"
                ystore = JupyterSQLiteYStore(path=updates_file_path)  # FIXME: pass in config
                self.rooms[ws_path] = YRoom(ready=False, ystore=ystore)
            else:
                # it is a transient document (e.g. awareness)
                self.rooms[ws_path] = YRoom()
        room = self.rooms[ws_path]
        await self.start_room(room)
        return room
