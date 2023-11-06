from __future__ import annotations

from contextlib import AsyncExitStack
from logging import Logger, getLogger

from anyio import TASK_STATUS_IGNORED, Event, create_task_group
from anyio.abc import TaskGroup, TaskStatus
from pycrdt import Doc

from .websocket import Websocket
from .yroom import YRoom


class WebsocketServer:
    """WebSocket server."""

    auto_clean_rooms: bool
    rooms: dict[str, YRoom]
    _started: Event | None
    _starting: bool
    _task_group: TaskGroup | None

    def __init__(
        self, rooms_ready: bool = True, auto_clean_rooms: bool = True, log: Logger | None = None
    ) -> None:
        """Initialize the object.

        The WebsocketServer instance should preferably be used as an async context manager:
        ```py
        async with websocket_server:
            ...
        ```
        However, a lower-level API can also be used:
        ```py
        task = asyncio.create_task(websocket_server.start())
        await websocket_server.started.wait()
        ...
        websocket_server.stop()
        ```

        Arguments:
            rooms_ready: Whether rooms are ready to be synchronized when opened.
            auto_clean_rooms: Whether rooms should be deleted when no client is there anymore.
            log: An optional logger.
        """
        self.rooms_ready = rooms_ready
        self.auto_clean_rooms = auto_clean_rooms
        self.log = log or getLogger(__name__)
        self.rooms = {}
        self._started = None
        self._starting = False
        self._task_group = None

    @property
    def started(self) -> Event:
        """An async event that is set when the WebSocket server has started."""
        if self._started is None:
            self._started = Event()
        return self._started

    async def get_room(self, name: str, ydoc: Doc | None = None) -> YRoom:
        """Get or create a room with the given name, and start it.

        Arguments:
            name: The room name.

        Returns:
            The room with the given name, or a new one if no room with that name was found.
        """
        if name not in self.rooms.keys():
            self.rooms[name] = YRoom(ydoc=ydoc, ready=self.rooms_ready, log=self.log)
        room = self.rooms[name]
        await self.start_room(room)
        return room

    async def start_room(self, room: YRoom) -> None:
        """Start a room, if not already started.

        Arguments:
            room: The room to start.
        """
        if self._task_group is None:
            raise RuntimeError(
                "The WebsocketServer is not running: use `async with websocket_server:` "
                "or `await websocket_server.start()`"
            )

        if not room.started.is_set():
            await self._task_group.start(room.start)

    def get_room_name(self, room: YRoom) -> str:
        """Get the name of a room.

        Arguments:
            room: The room to get the name from.

        Returns:
            The room name.
        """
        return list(self.rooms.keys())[list(self.rooms.values()).index(room)]

    def rename_room(
        self, to_name: str, *, from_name: str | None = None, from_room: YRoom | None = None
    ) -> None:
        """Rename a room.

        Arguments:
            to_name: The new name of the room.
            from_name: The previous name of the room (if `from_room` is not passed).
            from_room: The room to be renamed (if `from_name` is not passed).
        """
        if from_name is not None and from_room is not None:
            raise RuntimeError("Cannot pass from_name and from_room")
        if from_name is None:
            assert from_room is not None
            from_name = self.get_room_name(from_room)
        self.rooms[to_name] = self.rooms.pop(from_name)

    def delete_room(self, *, name: str | None = None, room: YRoom | None = None) -> None:
        """Delete a room.

        Arguments:
            name: The name of the room to delete (if `room` is not passed).
            room: The room to delete ( if `name` is not passed).
        """
        if name is not None and room is not None:
            raise RuntimeError("Cannot pass name and room")
        if name is None:
            assert room is not None
            name = self.get_room_name(room)
        room = self.rooms.pop(name)
        room.stop()

    async def serve(self, websocket: Websocket) -> None:
        """Serve a client through a WebSocket.

        Arguments:
            websocket: The WebSocket through which to serve the client.
        """
        if self._task_group is None:
            raise RuntimeError(
                "The WebsocketServer is not running: use `async with websocket_server:` "
                "or `await websocket_server.start()`"
            )

        async with create_task_group() as tg:
            tg.start_soon(self._serve, websocket, tg)

    async def _serve(self, websocket: Websocket, tg: TaskGroup):
        room = await self.get_room(websocket.path)
        await self.start_room(room)
        await room.serve(websocket)

        if self.auto_clean_rooms and not room.clients:
            self.delete_room(room=room)
        tg.cancel_scope.cancel()

    async def __aenter__(self) -> WebsocketServer:
        if self._task_group is not None:
            raise RuntimeError("WebsocketServer already running")

        async with AsyncExitStack() as exit_stack:
            tg = create_task_group()
            self._task_group = await exit_stack.enter_async_context(tg)
            self._exit_stack = exit_stack.pop_all()
            self.started.set()

        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        if self._task_group is None:
            raise RuntimeError("WebsocketServer not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
        return await self._exit_stack.__aexit__(exc_type, exc_value, exc_tb)

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        """Start the WebSocket server.

        Arguments:
            task_status: The status to set when the task has started.
        """
        if self._starting:
            return
        else:
            self._starting = True

        if self._task_group is not None:
            raise RuntimeError("WebsocketServer already running")

        # create the task group and wait forever
        async with create_task_group() as self._task_group:
            self._task_group.start_soon(Event().wait)
            self.started.set()
            self._starting = False
            task_status.started()

    def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._task_group is None:
            raise RuntimeError("WebsocketServer not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
