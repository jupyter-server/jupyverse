from __future__ import annotations

from contextlib import AsyncExitStack
from functools import partial

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

from .websocket import Websocket
from .yutils import put_updates


class WebsocketProvider:
    _ydoc: Doc
    _update_send_stream: MemoryObjectSendStream
    _update_receive_stream: MemoryObjectReceiveStream
    _started: Event | None
    _starting: bool
    _task_group: TaskGroup | None

    def __init__(self, ydoc: Doc, websocket: Websocket, log: BoundLogger | None = None) -> None:
        self._ydoc = ydoc
        self._websocket = websocket
        self.log = log or get_logger()
        self._update_send_stream, self._update_receive_stream = create_memory_object_stream(
            max_buffer_size=65536
        )
        self._started = None
        self._starting = False
        self._task_group = None
        ydoc.observe(partial(put_updates, self._update_send_stream))

    @property
    def started(self) -> Event:
        if self._started is None:
            self._started = Event()
        return self._started

    async def __aenter__(self) -> WebsocketProvider:
        if self._task_group is not None:
            raise RuntimeError("WebsocketProvider already running")

        async with AsyncExitStack() as exit_stack:
            tg = create_task_group()
            self._task_group = await exit_stack.enter_async_context(tg)
            self._exit_stack = exit_stack.pop_all()
            tg.start_soon(self._run)
            self.started.set()

        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        if self._task_group is None:
            raise RuntimeError("WebsocketProvider not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
        return await self._exit_stack.__aexit__(exc_type, exc_value, exc_tb)

    async def _run(self):
        sync_message = create_sync_message(self._ydoc)
        self.log.debug(
            "Sending %s message to endpoint: %s",
            YSyncMessageType.SYNC_STEP1.name,
            self._websocket.path,
        )
        await self._websocket.send(sync_message)
        self._task_group.start_soon(self._send)
        async for message in self._websocket:
            if message[0] == YMessageType.SYNC:
                self.log.debug(
                    "Received message",
                    name=YSyncMessageType(message[1]).name,
                    endpoint=self._websocket.path,
                )
                reply = handle_sync_message(message[1:], self._ydoc)
                if reply is not None:
                    self.log.debug(
                        "Sending message",
                        name=YSyncMessageType.SYNC_STEP2.name,
                        endpoint=self._websocket.path,
                    )
                    await self._websocket.send(reply)

    async def _send(self):
        async with self._update_receive_stream:
            async for update in self._update_receive_stream:
                message = create_update_message(update)
                try:
                    await self._websocket.send(message)
                except Exception:
                    pass

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        if self._starting:
            return
        else:
            self._starting = True

        if self._task_group is not None:
            raise RuntimeError("WebsocketProvider already running")

        async with create_task_group() as self._task_group:
            self._task_group.start_soon(self._run)
            self.started.set()
            self._starting = False
            task_status.started()

    def stop(self):
        if self._task_group is None:
            raise RuntimeError("WebsocketProvider not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
