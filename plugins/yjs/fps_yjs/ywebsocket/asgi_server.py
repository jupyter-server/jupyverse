from __future__ import annotations

from inspect import isawaitable
from typing import Any, Awaitable, Callable

from .websocket_server import WebsocketServer


class ASGIWebsocket:
    def __init__(
        self,
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
        path: str,
        on_disconnect: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ):
        self._receive = receive
        self._send = send
        self._path = path
        self._on_disconnect = on_disconnect

    @property
    def path(self) -> str:
        return self._path

    def __aiter__(self):
        return self

    async def __anext__(self) -> bytes:
        return await self.recv()

    async def send(self, message: bytes) -> None:
        await self._send(
            dict(
                type="websocket.send",
                bytes=message,
            )
        )

    async def recv(self) -> bytes:
        message = await self._receive()
        if message["type"] == "websocket.receive":
            return message["bytes"]
        if message["type"] == "websocket.disconnect":
            if self._on_disconnect is not None:
                res = self._on_disconnect(message)
                if isawaitable(res):
                    await res
            raise StopAsyncIteration()
        return b""


class ASGIServer:
    """ASGI server."""

    def __init__(
        self,
        websocket_server: WebsocketServer,
        on_connect: Callable[[dict[str, Any], dict[str, Any]], Awaitable[bool] | bool]
        | None = None,
        on_disconnect: Callable[[dict[str, Any]], Awaitable[None] | None] | None = None,
    ):
        """Initialize the object.

        Arguments:
            websocket_server: An instance of WebsocketServer.
            on_connect: An optional callback to call when connecting the WebSocket.
                If the callback returns True, the WebSocket is not accepted.
            on_disconnect: An optional callback called when disconnecting the WebSocket.
        """
        self._websocket_server = websocket_server
        self._on_connect = on_connect
        self._on_disconnect = on_disconnect

    async def __call__(
        self,
        scope: dict[str, Any],
        receive: Callable[[], Awaitable[dict[str, Any]]],
        send: Callable[[dict[str, Any]], Awaitable[None]],
    ):
        msg = await receive()
        if msg["type"] == "websocket.connect":
            if self._on_connect is not None:
                close = self._on_connect(msg, scope)
                if isawaitable(close):
                    close = await close
                if close:
                    return

            await send({"type": "websocket.accept"})
            websocket = ASGIWebsocket(receive, send, scope["path"], self._on_disconnect)
            await self._websocket_server.serve(websocket)
