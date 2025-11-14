from __future__ import annotations

from anyio import TASK_STATUS_IGNORED, Event, create_task_group
from anyio.abc import TaskGroup, TaskStatus
from pycrdt import Doc
from structlog import BoundLogger, get_logger

from .websocket import Websocket
from .yroom import YRoom


class WebsocketServer:
    auto_clean_rooms: bool
    rooms: dict[str, YRoom]
    _task_group: TaskGroup

    def __init__(
        self,
        rooms_ready: bool = True,
        auto_clean_rooms: bool = True,
        log: BoundLogger | None = None,
    ) -> None:
        self.rooms_ready = rooms_ready
        self.auto_clean_rooms = auto_clean_rooms
        self.log = log or get_logger()
        self.rooms = {}

    async def get_room(self, name: str, ydoc: Doc | None = None) -> YRoom:
        if name not in self.rooms.keys():
            self.rooms[name] = YRoom(ydoc=ydoc, ready=self.rooms_ready, log=self.log)
        room = self.rooms[name]
        await self.start_room(room)
        return room

    async def start_room(self, room: YRoom) -> None:
        if not room.started.is_set():
            await self._task_group.start(room.start)

    def get_room_name(self, room: YRoom) -> str:
        return list(self.rooms.keys())[list(self.rooms.values()).index(room)]

    def rename_room(
        self, to_name: str, *, from_name: str | None = None, from_room: YRoom | None = None
    ) -> None:
        if from_name is not None and from_room is not None:
            raise RuntimeError("Cannot pass from_name and from_room")
        if from_name is None:
            assert from_room is not None
            from_name = self.get_room_name(from_room)
        self.rooms[to_name] = self.rooms.pop(from_name)

    def delete_room(self, *, name: str | None = None, room: YRoom | None = None) -> None:
        if name is not None and room is not None:
            raise RuntimeError("Cannot pass name and room")
        if name is None:
            assert room is not None
            name = self.get_room_name(room)
        room = self.rooms.pop(name)
        room.stop()

    async def serve(self, websocket: Websocket, stop_event: Event | None = None) -> None:
        async with create_task_group() as tg:
            tg.start_soon(self._serve, websocket, tg)
            if stop_event is not None:
                tg.start_soon(self._watch_stop, tg, stop_event)

    async def _watch_stop(self, tg: TaskGroup, stop_event: Event):
        await stop_event.wait()
        tg.cancel_scope.cancel()

    async def _serve(self, websocket: Websocket, tg: TaskGroup):
        room = await self.get_room(websocket.path)
        await self.start_room(room)
        await room.serve(websocket)

        if self.auto_clean_rooms and not room.clients:
            self.delete_room(room=room)
        tg.cancel_scope.cancel()

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        # create the task group and wait forever
        async with create_task_group() as tg:
            self._task_group = tg
            tg.start_soon(Event().wait)
            task_status.started()

    async def stop(self) -> None:
        self._task_group.cancel_scope.cancel()
