import sys
from contextlib import AsyncExitStack
from types import TracebackType

from anyio import create_task_group, get_cancelled_exc_class, sleep_forever
from anyio.abc import TaskStatus
from httpx import Cookies
from httpx_ws import AsyncWebSocketSession, aconnect_ws
from pycrdt import (
    Doc,
    YMessageType,
    YSyncMessageType,
    create_sync_message,
    create_update_message,
    handle_sync_message,
)

from .channel import AsyncChannel, AsyncWebSocket

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class AsyncClient:
    def __init__(
        self,
        channel: AsyncChannel,
        doc: Doc | None = None,
    ) -> None:
        """
        Creates an async client that connects to a server. The client must always
                be used with an async context manager, for instance:
                ```py
                async with AsyncWebsocketClient(url="ws://localhost:8000") as client:
                    ...
                ```

                Args:
                    channel: The async channel used to communicate with the server.
                    doc: An optional external shared document (or a new one will be created).
        """
        self._channel = channel
        self._doc: Doc = Doc() if doc is None else doc

    async def _run(self, *, task_status: TaskStatus[None]):
        async with self._doc.new_transaction():
            sync_message = create_sync_message(self._doc)
        await self._channel.send(sync_message)
        async for message in self._channel:
            if message[0] == YMessageType.SYNC:
                async with self._doc.new_transaction():
                    reply = handle_sync_message(message[1:], self._doc)
                if reply is not None:
                    await self._channel.send(reply)
                if message[1] == YSyncMessageType.SYNC_STEP2:
                    await self._task_group.start(self._send_updates)
                    task_status.started()

    async def _send_updates(self, *, task_status: TaskStatus[None]):
        async with self._doc.events() as events:
            task_status.started()
            async for event in events:
                message = create_update_message(event.update)
                await self._channel.send(message)

    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as exit_stack:
            self._task_group = await exit_stack.enter_async_context(create_task_group())
            await self._task_group.start(self._run)
            self._exit_stack = exit_stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        self._task_group.cancel_scope.cancel()
        return await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)


class AsyncWebSocketClient:
    def __init__(
        self,
        id: str = "",
        doc: Doc | None = None,
        *,
        url: str,
        cookies: Cookies | None = None,
    ) -> None:
        self._id = id
        self._doc = doc
        self._url = url
        self._cookies = cookies

    async def _aconnect_ws(self, *, task_status: TaskStatus[None]) -> None:
        try:
            ws: AsyncWebSocketSession
            async with aconnect_ws(
                f"{self._url}/{self._id}",
                keepalive_ping_interval_seconds=None,
                cookies=self._cookies,
            ) as ws:
                self._channel = AsyncWebSocket(ws, self._id)
                task_status.started()
                await sleep_forever()
        except get_cancelled_exc_class():
            pass

    async def __aenter__(self) -> Self:
        async with AsyncExitStack() as exit_stack:
            self._task_group = await exit_stack.enter_async_context(create_task_group())
            await self._task_group.start(self._aconnect_ws)
            self._client = await exit_stack.enter_async_context(
                AsyncClient(self._channel, self._doc)
            )
            self._exit_stack = exit_stack.pop_all()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> bool | None:
        self._task_group.cancel_scope.cancel()
        return await self._exit_stack.__aexit__(exc_type, exc_val, exc_tb)
