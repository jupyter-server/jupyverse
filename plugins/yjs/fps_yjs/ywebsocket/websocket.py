from typing import Protocol


class Websocket(Protocol):
    """WebSocket.

    The Websocket instance can receive messages using an async iterator,
    until the connection is closed:
    ```py
    async for message in websocket:
        ...
    ```
    Or directly by calling `recv()`:
    ```py
    message = await websocket.recv()
    ```
    Sending messages is done with `send()`:
    ```py
    await websocket.send(message)
    ```
    """

    @property
    def path(self) -> str:
        """The WebSocket path."""
        ...

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        try:
            message = await self.recv()
        except Exception:
            raise StopAsyncIteration()

        return message

    async def send(self, message: bytes) -> None:
        """Send a message.

        Arguments:
            message: The message to send.
        """
        ...

    async def recv(self) -> bytes:
        """Receive a message.

        Returns:
            The received message.
        """
        ...
