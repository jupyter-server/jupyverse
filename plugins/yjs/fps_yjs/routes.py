import re
import time
import uuid
from enum import IntEnum
from typing import Dict, Set

from fps.hooks import register_router  # type: ignore
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, status
import fastapi

from fps_auth.backends import cookie_authentication  # type: ignore
from fps_auth.db import get_user_db  # type: ignore
from fps_auth.config import get_auth_config  # type: ignore

router = APIRouter()


def get_path_param_names(path: str) -> Set[str]:
    return {name.split(":")[0] for name in re.findall("{(.*?)}", path)}


# FIXME: remove the patch when https://github.com/tiangolo/fastapi/pull/3879 is merged
fastapi.utils.get_path_param_names.__code__ = get_path_param_names.__code__


@router.websocket("/api/yjs/{type}:{path:path}")
async def websocket_endpoint(
    websocket: WebSocket,
    type,
    path,
    auth_config=Depends(get_auth_config),
    user_db=Depends(get_user_db),
):
    accept_websocket = False
    if auth_config.mode == "noauth":
        accept_websocket = True
    elif "fastapiusersauth" in websocket._cookies:
        cookie = websocket._cookies["fastapiusersauth"]
        user = await cookie_authentication(cookie, user_db)
        if user:
            accept_websocket = True
    if accept_websocket:
        await websocket.accept()
        socket = YjsEchoWebSocket(websocket)
        await socket.open(path)
    else:
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)


# The y-protocol defines messages types that just need to be propagated to all other peers.
# Here, we define some additional messageTypes that the server can interpret.
# Messages that the server can't interpret should be broadcasted to all other clients.


class ServerMessageType(IntEnum):
    # The client is asking for a lock. Should return a lock-identifier if one is available.
    ACQUIRE_LOCK = 127
    # The client is asking to release a lock to make it available to other users again.
    RELEASE_LOCK = 126
    # The client is asking to retrieve the initial state of the Yjs document. Return an empty buffer
    # when nothing is available.
    REQUEST_INITIALIZED_CONTENT = 125
    # The client retrieved an empty "initial content" and generated the initial state of the
    # document after acquiring a lock. Store this.
    PUT_INITIALIZED_CONTENT = 124
    # The client moved the document to a different location. After receiving this message, we make
    # the current document available under a different url.
    # The other clients are automatically notified of this change because the path is shared through
    # the Yjs document as well.
    RENAME_SESSION = 123


class YjsRoom:
    def __init__(self):
        self.lock = None
        self.clients = {}
        self.content = bytes([])


class YjsEchoWebSocket:
    rooms: Dict[str, YjsRoom] = {}

    def __init__(self, websocket):
        self.websocket = websocket

    async def open(self, guid):
        # print("[YJSEchoWS]: open", guid)
        cls = self.__class__
        self.room_id = guid
        self.id = str(uuid.uuid4())
        room = cls.rooms.get(self.room_id)
        if room is None:
            room = YjsRoom()
            cls.rooms[self.room_id] = room
        room.clients[self.id] = self
        # Send SyncStep1 message (based on y-protocols)
        await self.websocket.send_bytes(bytes([0, 0, 1, 0]))

        try:
            while True:
                message = await self.websocket.receive_bytes()
                # print("[YJSEchoWS]: message, ", message)
                cls = self.__class__
                room_id = self.room_id
                room = cls.rooms.get(room_id)
                if message[0] == ServerMessageType.ACQUIRE_LOCK:
                    now = int(time.time())
                    if room.lock is None or now - room.lock > 15:  # no lock or timeout
                        room.lock = now
                        # print('Acquired new lock: ', room.lock)
                        # return acquired lock
                        await self.websocket.send_bytes(
                            bytes([ServerMessageType.ACQUIRE_LOCK])
                            + room.lock.to_bytes(4, byteorder="little")
                        )
                elif message[0] == ServerMessageType.RELEASE_LOCK:
                    releasedLock = int.from_bytes(message[1:], byteorder="little")
                    # print("trying release lock: ", releasedLock)
                    if room.lock == releasedLock:
                        # print('released lock: ', room.lock)
                        room.lock = None
                elif message[0] == ServerMessageType.REQUEST_INITIALIZED_CONTENT:
                    # print("client requested initial content")
                    await self.websocket.send_bytes(
                        bytes([ServerMessageType.REQUEST_INITIALIZED_CONTENT])
                        + room.content
                    )
                elif message[0] == ServerMessageType.PUT_INITIALIZED_CONTENT:
                    # print("client put initialized content")
                    room.content = message[1:]
                elif message[0] == ServerMessageType.RENAME_SESSION:
                    # We move the room to a different entry and also change the room_id property of
                    # each connected client
                    new_room_id = message[1:].decode("utf-8")
                    for client_id, client in room.clients.items():
                        client.room_id = new_room_id
                    cls.rooms.pop(room_id)
                    cls.rooms[new_room_id] = room
                    # print("renamed room to " + new_room_id + ". Old room name was " + room_id)
                elif room:
                    for client_id, client in room.clients.items():
                        if self.id != client_id:
                            await client.websocket.send_bytes(message)
        except WebSocketDisconnect:
            # print("[YJSEchoWS]: close")
            cls = self.__class__
            room = cls.rooms.get(self.room_id)
            room.clients.pop(self.id)
            if len(room.clients) == 0:
                cls.rooms.pop(self.room_id)
                # print("[YJSEchoWS]: close room " + self.room_id)


r = register_router(router)
