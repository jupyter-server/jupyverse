import sys
from abc import ABC, abstractmethod
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from functools import partial
from typing import TYPE_CHECKING, Any

from anyio import (
    AsyncContextManagerMixin,
    Event,
    create_task_group,
)
from anyio.abc import TaskGroup, TaskStatus
from anyioutils import ResourceLock
from pycrdt import (
    Doc,
    create_sync_message,
    create_update_message,
)

from .channel import AsyncChannel

if TYPE_CHECKING:
    from jupyter_ydoc.ybasedoc import YBaseDoc

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class YRoom(ABC, AsyncContextManagerMixin):
    _jupyter_ydoc: "YBaseDoc"

    def __init__(self, id: str, sync: bool = True, doc: Doc | None = None) -> None:
        """
        Creates a new room in which clients with the same ID will be connected.

        Args:
            id: The room ID.
            sync: Whether to start synchronizing clients right away.
        """
        self._id = id
        self._sync = sync
        self._doc: Doc = Doc() if doc is None else doc
        self._clients: set[AsyncChannel] = set()
        self._close_event = Event()

    @property
    def clients(self) -> set[AsyncChannel]:
        return self._clients

    @property
    def synced(self) -> bool:
        return self._sync

    @property
    def id(self) -> str:
        """
        Returns:
            The room ID.
        """
        return self._id

    @property
    def doc(self) -> Doc:
        """
        Returns:
            The room's shared document.
        """
        return self._doc

    @property
    def jupyter_ydoc(self) -> "YBaseDoc":
        """
        Returns:
            The room's Jupyter YDoc.
        """
        return self._jupyter_ydoc

    @property
    def task_group(self) -> TaskGroup:
        """
        Returns:
            The room's task group, that can be used to launch background tasks.
        """
        return self._task_group

    @asynccontextmanager
    async def __asynccontextmanager__(self) -> AsyncGenerator[Self]:
        async with create_task_group() as self._task_group:
            if self._sync:
                await self._task_group.start(self.run)
            yield self
            await self._close_event.wait()
            self._task_group.cancel_scope.cancel()

    async def sync(self):
        if not self._sync:
            self._sync = True
            await self._task_group.start(self.run)

    async def run(self, *, task_status: TaskStatus[None]) -> None:
        """
        The main background task which is responsible for forwarding every update
        from a client to all other clients in the room.

        Args:
            task_status: The task status that is set when the task has started.
        """
        async with self._doc.events() as events:
            task_status.started()
            async for event in events:
                if self._clients:
                    message = create_update_message(event.update)
                    for client in set(self._clients):
                        try:
                            await client.send(message)
                        except Exception:
                            await self._remove_client(client)

    async def serve(self, client: AsyncChannel) -> None:
        """
        The handler for a client which is responsible for the connection handshake and
        for applying the client updates to the room's shared document.

        Args:
            client: The client making the connection.
        """
        self._clients.add(client)
        try:
            async with self._doc.new_transaction():
                sync_message = create_sync_message(self._doc)
            await client.send(sync_message)
            async for message in client:
                await self.handle_message(message, client)
        except Exception:
            pass
        finally:
            await self._remove_client(client)

    async def _remove_client(self, client: AsyncChannel) -> None:
        self._clients.discard(client)
        if not self._clients:
            self.task_group.start_soon(self.close)

    async def close(self) -> None:
        self._close_event.set()

    @abstractmethod
    async def handle_message(self, message: bytes, client: AsyncChannel) -> None: ...


class YRoomFactory:
    def __init__(self, yroom_factory: type[YRoom]) -> None:
        self._yroom_factory = yroom_factory

    def __call__(self, *args: Any, **kwargs: Any) -> YRoom:
        return self._yroom_factory(*args, **kwargs)


class YRooms(AsyncContextManagerMixin):
    def __init__(self, room_factory: Callable[[str], YRoom] = YRoom) -> None:
        self._room_factory = room_factory
        self._rooms: dict[str, YRoom] = {}
        self._lock = ResourceLock()

    @property
    def task_group(self) -> TaskGroup:
        """
        Returns:
            The room's task group, that can be used to launch background tasks.
        """
        return self._task_group

    @asynccontextmanager
    async def __asynccontextmanager__(self) -> AsyncGenerator[Self]:
        async with create_task_group() as self._task_group:
            yield self
            self._task_group.cancel_scope.cancel()

    async def _create_room(self, id: str, *, task_status: TaskStatus[YRoom], **kwargs: Any):
        async with self._room_factory(id, **kwargs) as room:
            task_status.started(room)
            await room._close_event.wait()
            del self._rooms[id]

    async def get_room(self, id: str, **kwargs: Any) -> YRoom:
        async with self._lock(id):
            if id not in self._rooms:
                room = await self._task_group.start(partial(self._create_room, id, **kwargs))
                self._rooms[id] = room
            else:
                room = self._rooms[id]
        return room

    async def serve(self, channel: AsyncChannel, **kwargs: Any) -> None:
        room = await self.get_room(channel.id, **kwargs)
        await room.serve(channel)
