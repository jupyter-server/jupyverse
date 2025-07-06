from __future__ import annotations

from collections.abc import Awaitable
from contextlib import AsyncExitStack
from functools import partial
from inspect import isawaitable
from typing import Callable

from anyio import (
    TASK_STATUS_IGNORED,
    Event,
    create_memory_object_stream,
    create_task_group,
)
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from pycrdt import (
    Doc,
    YMessageType,
    YSyncMessageType,
    create_sync_message,
    create_update_message,
    handle_sync_message,
)
from structlog import BoundLogger, get_logger

from .awareness import Awareness
from .websocket import Websocket
from .ystore import BaseYStore
from .yutils import put_updates


class YRoom:
    clients: list
    ydoc: Doc
    ystore: BaseYStore | None
    _on_message: Callable[[bytes, Websocket], Awaitable[bool] | bool] | None
    _update_send_stream: MemoryObjectSendStream
    _update_receive_stream: MemoryObjectReceiveStream
    _ready: bool
    _task_group: TaskGroup | None
    _started: Event | None
    _starting: bool

    def __init__(
        self,
        ydoc: Doc | None = None,
        ready: bool = True,
        ystore: BaseYStore | None = None,
        log: BoundLogger | None = None,
    ):
        """Initialize the object.

        The YRoom instance should preferably be used as an async context manager:
        ```py
        async with room:
            ...
        ```
        However, a lower-level API can also be used:
        ```py
        task = asyncio.create_task(room.start())
        await room.started.wait()
        ...
        room.stop()
        ```

        Arguments:
            ready: Whether the internal YDoc is ready to be synchronized right away.
            ystore: An optional store in which to persist document updates.
            log: An optional logger.
        """
        self.ydoc = Doc() if ydoc is None else ydoc
        self.awareness = Awareness(self.ydoc)
        self._update_send_stream, self._update_receive_stream = create_memory_object_stream(
            max_buffer_size=65536
        )
        self._ready = False
        self.ready = ready
        self.ystore = ystore
        self.log = log or get_logger()
        self.clients = []
        self._on_message = None
        self._started = None
        self._starting = False
        self._task_group = None

    @property
    def started(self):
        """An async event that is set when the YRoom provider has started."""
        if self._started is None:
            self._started = Event()
        return self._started

    @property
    def ready(self) -> bool:
        """
        Returns:
            True is the internal YDoc is ready to be synchronized.
        """
        return self._ready

    @ready.setter
    def ready(self, value: bool) -> None:
        """
        Arguments:
            value: True if the internal YDoc is ready to be synchronized, False otherwise."""
        self._ready = value
        if value:
            self.ydoc.observe(partial(put_updates, self._update_send_stream))

    @property
    def on_message(self) -> Callable[[bytes, Websocket], Awaitable[bool] | bool] | None:
        """
        Returns:
            The optional callback to call when a message is received.
        """
        return self._on_message

    @on_message.setter
    def on_message(self, value: Callable[[bytes, Websocket], Awaitable[bool] | bool] | None):
        """
        Arguments:
            value: An optional callback to call when a message is received.
                If the callback returns True, the message is skipped.
        """
        self._on_message = value

    async def _broadcast_updates(self):
        if self.ystore is not None and not self.ystore.started.is_set():
            self._task_group.start_soon(self.ystore.start)

        async with self._update_receive_stream:
            async for update in self._update_receive_stream:
                if self._task_group.cancel_scope.cancel_called:
                    return
                # broadcast internal ydoc's update to all clients, that includes changes from the
                # clients and changes from the backend (out-of-band changes)
                for client in self.clients:
                    self.log.debug(
                        "Sending Y update to client",
                        endpoint=client.path,
                    )
                    message = create_update_message(update)
                    self._task_group.start_soon(client.send, message)
                if self.ystore:
                    self.log.debug("Writing Y update to YStore")
                    self._task_group.start_soon(self.ystore.write, update)

    async def __aenter__(self) -> YRoom:
        if self._task_group is not None:
            raise RuntimeError("YRoom already running")

        async with AsyncExitStack() as exit_stack:
            tg = create_task_group()
            self._task_group = await exit_stack.enter_async_context(tg)
            self._exit_stack = exit_stack.pop_all()
            tg.start_soon(self._broadcast_updates)
            self.started.set()

        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        if self._task_group is None:
            raise RuntimeError("YRoom not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
        return await self._exit_stack.__aexit__(exc_type, exc_value, exc_tb)

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        """Start the room.

        Arguments:
            task_status: The status to set when the task has started.
        """
        if self._starting:
            return
        else:
            self._starting = True

        if self._task_group is not None:
            raise RuntimeError("YRoom already running")

        async with create_task_group() as self._task_group:
            self._task_group.start_soon(self._broadcast_updates)
            self.started.set()
            self._starting = False
            task_status.started()

    def stop(self):
        """Stop the room."""
        if self._task_group is None:
            raise RuntimeError("YRoom not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None

    async def serve(self, websocket: Websocket):
        async with create_task_group() as tg:
            self.clients.append(websocket)
            sync_message = create_sync_message(self.ydoc)
            self.log.debug(
                "Sending message",
                name=YSyncMessageType.SYNC_STEP1.name,
                endpoint=websocket.path,
            )
            await websocket.send(sync_message)
            try:
                async for message in websocket:
                    # filter messages (e.g. awareness)
                    skip = False
                    if self.on_message:
                        _skip = self.on_message(message, websocket)
                        skip = await _skip if isawaitable(_skip) else _skip
                    if skip:
                        continue
                    message_type = message[0]
                    if message_type == YMessageType.SYNC:
                        # update our internal state in the background
                        # changes to the internal state are then forwarded to all clients
                        # and stored in the YStore (if any)
                        reply = handle_sync_message(message[1:], self.ydoc)
                        if reply is not None:
                            self.log.debug(
                                "Sending message",
                                name=YSyncMessageType.SYNC_STEP2.name,
                                endpoint=websocket.path,
                            )
                            tg.start_soon(websocket.send, reply)
                    elif message_type == YMessageType.AWARENESS:
                        # forward awareness messages from this client to all clients,
                        # including itself, because it's used to keep the connection alive
                        self.log.debug(
                            "Received message",
                            name=YMessageType.AWARENESS.name,
                            endpoint=websocket.path,
                        )
                        for client in self.clients:
                            self.log.debug(
                                "Sending Y awareness",
                                from_endpoint=websocket.path,
                                to_endpoint=client.path,
                            )
                            tg.start_soon(client.send, message)
            except Exception as e:
                self.log.debug(
                    "Error serving",
                    endpoint=websocket.path,
                    exc_info=e,
                )

            # remove this client
            self.clients = [c for c in self.clients if c != websocket]
