from abc import ABC, abstractmethod
from typing import Protocol

from anyio import Lock


class AsyncChannel(ABC):
    """A transport-agnostic asynchronous channel used to synchronize a document.
    An example of a channel is a WebSocket.

    Messages can be received through the channel using an async iterator,
    until the connection is closed:
    ```py
    async for message in channel:
        ...
    ```
    Or directly by calling `receive()`:
    ```py
    message = await channel.receive()
    ```
    Sending messages is done with `send()`:
    ```py
    await channel.send(message)
    ```
    """

    @property
    @abstractmethod
    def id(self) -> str:
        """The channel ID."""
        ...

    def __aiter__(self) -> "AsyncChannel":
        return self

    async def __anext__(self) -> bytes:
        return await self.receive()

    @abstractmethod
    async def send(self, message: bytes) -> None:
        """Sends a message.

        Args:
            message: The message to send.
        """
        ...

    @abstractmethod
    async def receive(self) -> bytes:
        """Receives a message.

        Returns:
            The received message.
        """
        ...


class _AsyncWebSocket(Protocol):
    async def send_bytes(self, message: bytes) -> None: ...

    async def receive_bytes(self) -> bytes: ...


class AsyncWebSocket(AsyncChannel):
    """Typically a `starlette.websockets.WebSocket` (server side) or an
    `httpx_ws.AsyncWebSocketSession` (client side).
    """

    def __init__(self, websocket: _AsyncWebSocket, id: str) -> None:
        self._websocket = websocket
        self._id = id
        self._send_lock = Lock()

    async def __anext__(self) -> bytes:
        try:
            message = await self.receive()
        except Exception:
            raise StopAsyncIteration()

        return message

    @property
    def id(self) -> str:
        return self._id

    async def send(self, message: bytes) -> None:
        async with self._send_lock:
            await self._websocket.send_bytes(message)

    async def receive(self) -> bytes:
        return bytes(await self._websocket.receive_bytes())
