from __future__ import annotations

from contextlib import AsyncExitStack
from functools import partial
from logging import Logger, getLogger

from anyio import (
    TASK_STATUS_IGNORED,
    Event,
    create_memory_object_stream,
    create_task_group,
)
from anyio.abc import TaskGroup, TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from pycrdt import Doc

from .websocket import Websocket
from .yutils import (
    YMessageType,
    create_update_message,
    process_sync_message,
    put_updates,
    sync,
)


class WebsocketProvider:
    """WebSocket provider."""

    _ydoc: Doc
    _update_send_stream: MemoryObjectSendStream
    _update_receive_stream: MemoryObjectReceiveStream
    _started: Event | None
    _starting: bool
    _task_group: TaskGroup | None

    def __init__(self, ydoc: Doc, websocket: Websocket, log: Logger | None = None) -> None:
        """Initialize the object.

        The WebsocketProvider instance should preferably be used as an async context manager:
        ```py
        async with websocket_provider:
            ...
        ```
        However, a lower-level API can also be used:
        ```py
        task = asyncio.create_task(websocket_provider.start())
        await websocket_provider.started.wait()
        ...
        websocket_provider.stop()
        ```

        Arguments:
            ydoc: The YDoc to connect through the WebSocket.
            websocket: The WebSocket through which to connect the YDoc.
            log: An optional logger.
        """
        self._ydoc = ydoc
        self._websocket = websocket
        self.log = log or getLogger(__name__)
        self._update_send_stream, self._update_receive_stream = create_memory_object_stream(
            max_buffer_size=65536
        )
        self._started = None
        self._starting = False
        self._task_group = None
        ydoc.observe(partial(put_updates, self._update_send_stream))

    @property
    def started(self) -> Event:
        """An async event that is set when the WebSocket provider has started."""
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
        await sync(self._ydoc, self._websocket, self.log)
        self._task_group.start_soon(self._send)
        async for message in self._websocket:
            if message[0] == YMessageType.SYNC:
                await process_sync_message(message[1:], self._ydoc, self._websocket, self.log)

    async def _send(self):
        async with self._update_receive_stream:
            async for update in self._update_receive_stream:
                message = create_update_message(update)
                try:
                    await self._websocket.send(message)
                except Exception:
                    pass

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        """Start the WebSocket provider.

        Arguments:
            task_status: The status to set when the task has started.
        """
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
        """Stop the WebSocket provider."""
        if self._task_group is None:
            raise RuntimeError("WebsocketProvider not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
