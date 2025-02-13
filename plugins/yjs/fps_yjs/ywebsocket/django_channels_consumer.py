from __future__ import annotations

from typing import TypedDict

from channels.generic.websocket import AsyncWebsocketConsumer  # type: ignore
from pycrdt import Doc, YMessageType, YSyncMessageType, create_sync_message, handle_sync_message
from structlog import get_logger

from .websocket import Websocket

logger = get_logger()


class _WebsocketShim(Websocket):
    def __init__(self, path, send_func) -> None:
        self._path = path
        self._send_func = send_func

    @property
    def path(self) -> str:
        return self._path

    def __aiter__(self):
        raise NotImplementedError()

    async def __anext__(self) -> bytes:
        raise NotImplementedError()

    async def send(self, message: bytes) -> None:
        await self._send_func(message)

    async def recv(self) -> bytes:
        raise NotImplementedError()


class YjsConsumer(AsyncWebsocketConsumer):
    """A working consumer for [Django Channels](https://github.com/django/channels).

    This consumer can be used out of the box simply by adding:
    ```py
    path("ws/<str:room>", YjsConsumer.as_asgi())
    ```
    to your `urls.py` file. In practice, once you
    [set up Channels](https://channels.readthedocs.io/en/1.x/getting-started.html),
    you might have something like:
    ```py
    # urls.py
    from django.urls import path
    from backend.consumer import DocConsumer, UpdateConsumer

    urlpatterns = [
        path("ws/<str:room>", YjsConsumer.as_asgi()),
    ]

    # asgi.py
    import os
    from channels.routing import ProtocolTypeRouter, URLRouter
    from urls import urlpatterns

    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "backend.settings")

    application = ProtocolTypeRouter({
        "websocket": URLRouter(urlpatterns_ws),
    })
    ```

    Additionally, the consumer can be subclassed to customize its behavior.

    In particular,

    - Override `make_room_name` to customize the room name.
    - Override `make_ydoc` to initialize the YDoc. This is useful to initialize it with data
      from your database, or to add observers to it).
    - Override `connect` to do custom validation (like auth) on connect,
      but be sure to call `await super().connect()` in the end.
    - Call `group_send_message` to send a message to an entire group/room.
    - Call `send_message` to send a message to a single client, although this is not recommended.

    A full example of a custom consumer showcasing all of these options is:
    ```py
    from pycrdt import Doc
    from asgiref.sync import async_to_sync
    from channels.layers import get_channel_layer
    from ypy_websocket.django_channels_consumer import YjsConsumer
    from ypy_websocket.yutils import create_update_message


    class DocConsumer(YjsConsumer):
        def make_room_name(self) -> str:
            # modify the room name here
            return self.scope["url_route"]["kwargs"]["room"]

        async def make_ydoc(self) -> Doc:
            doc = Doc()
            # fill doc with data from DB here
            doc.observe(self.on_update_event)
            return doc

        async def connect(self):
            user = self.scope["user"]
            if user is None or user.is_anonymous:
                await self.close()
                return
            await super().connect()

        def on_update_event(self, event):
            # process event here
            ...

        async def doc_update(self, update_wrapper):
            update = update_wrapper["update"]
            self.ydoc.apply_update(update)
            await self.group_send_message(create_update_message(update))


    def send_doc_update(room_name, update):
        layer = get_channel_layer()
        async_to_sync(layer.group_send)(room_name, {"type": "doc_update", "update": update})
    ```

    """

    def __init__(self):
        super().__init__()
        self.room_name = None
        self.ydoc = None
        self._websocket_shim = None

    def make_room_name(self) -> str:
        """Make the room name for a new channel.

        Override to customize the room name when a channel is created.

        Returns:
            The room name for a new channel. Defaults to the room name from the URL route.
        """
        return self.scope["url_route"]["kwargs"]["room"]

    async def make_ydoc(self) -> Doc:
        """Make the YDoc for a new channel.

        Override to customize the YDoc when a channel is created
        (useful to initialize it with data from your database, or to add observers to it).

        Returns:
            The YDoc for a new channel. Defaults to a new empty YDoc.
        """
        return Doc()

    def _make_websocket_shim(self, path: str) -> _WebsocketShim:
        return _WebsocketShim(path, self.group_send_message)

    async def connect(self) -> None:
        self.room_name = self.make_room_name()
        self.ydoc = await self.make_ydoc()
        self._websocket_shim = self._make_websocket_shim(self.scope["path"])

        await self.channel_layer.group_add(self.room_name, self.channel_name)
        await self.accept()

        sync_message = create_sync_message(self.ydoc)
        logger.debug(
            "Sending message",
            name=YSyncMessageType.SYNC_STEP1.name,
            endpoint=self._websocket_shim.path,
        )
        await self._websocket_shim.send(sync_message)

    async def disconnect(self, code) -> None:
        await self.channel_layer.group_discard(self.room_name, self.channel_name)

    async def receive(self, text_data=None, bytes_data=None):
        if bytes_data is None:
            return
        await self.group_send_message(bytes_data)
        if bytes_data[0] != YMessageType.SYNC:
            return
        reply = handle_sync_message(bytes_data[1:], self.ydoc)
        if reply is not None:
            logger.debug(
                "Sending message",
                name=YSyncMessageType.SYNC_STEP2.name,
                endpoint=self._websocket_shim.path,
            )
            await self._websocket_shim.send(reply)

    class WrappedMessage(TypedDict):
        """A wrapped message to send to the client."""

        message: bytes

    async def send_message(self, message_wrapper: WrappedMessage) -> None:
        """Send a message to the client.

        Arguments:
            message_wrapper: The message to send, wrapped.
        """
        await self.send(bytes_data=message_wrapper["message"])

    async def group_send_message(self, message: bytes) -> None:
        """Send a message to the group.

        Arguments:
            message: The message to send.
        """
        await self.channel_layer.group_send(
            self.room_name, {"type": "send_message", "message": message}
        )
