import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from socket import socket
from typing import Any
from urllib.parse import parse_qs
from uuid import uuid4

from anyio import (
    AsyncContextManagerMixin,
    Event,
    create_task_group,
    fail_after,
    open_process,
    sleep,
    sleep_forever,
)
from anyio.abc import TaskStatus
from anyio.streams.text import TextReceiveStream
from fastapi import APIRouter, Depends, Request, WebSocket
from httpx import AsyncClient, ConnectError, Cookies, Response
from httpx_ws import AsyncWebSocketSession, aconnect_ws
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from structlog import get_logger

from jupyverse_api import Router

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self

logger = get_logger()


class JupyterServer(Router, AsyncContextManagerMixin):
    def __init__(self, app: App, auth: Auth, stop_event: Event):
        super().__init__(app=app)
        self._auth = auth
        self._stop_event = stop_event
        self._port = get_unused_tcp_port()

    @asynccontextmanager
    async def __asynccontextmanager__(self) -> AsyncGenerator[Self]:
        async with create_task_group() as self._task_group:
            await self._task_group.start(self._run)
            yield self
            await self._stop_event.wait()
            self._task_group.cancel_scope.cancel()
            self._process.terminate()
            await self._process.wait()

    async def _run(self, *, task_status: TaskStatus[None]):
        self._token = uuid4().hex
        async with (
            await open_process(
                [
                    "jupyter",
                    "server",
                    f"--IdentityProvider.token={self._token}",
                    "--port",
                    str(self._port),
                ]
            ) as self._process,
            AsyncClient() as client,
        ):
            self._client = _AsyncClient(client, self._port)
            self._task_group.start_soon(self._show_stdout)
            self._task_group.start_soon(self._show_stderr)
            with fail_after(10):
                while True:
                    await sleep(0.1)
                    try:
                        response = await self._client.get("/", params={"token": self._token})
                        if response.status_code == 200:
                            break
                    except ConnectError:
                        pass
            task_status.started()
            await sleep_forever()

    async def _show_stdout(self) -> None:
        async for text in TextReceiveStream(self._process.stdout):
            logger.debug(text)

    async def _show_stderr(self) -> None:
        async for text in TextReceiveStream(self._process.stderr):
            logger.debug(text)

    def proxy(self, root_path: str) -> None:
        router = APIRouter()

        @router.get(root_path + "/{path:path}")
        async def get(
            request: Request,
            user: User = Depends(self._auth.current_user()),
        ) -> dict[str, Any]:
            params = parse_qs(request.url.query)
            response = await self._client.get(request.url.path, params=params)
            return response.json()

        @router.post(root_path + "/{path:path}")
        async def post(
            request: Request,
            user: User = Depends(self._auth.current_user()),
        ) -> dict[str, Any]:
            params = parse_qs(request.url.query)
            content = await request.body()
            response = await self._client.post(request.url.path, params=params, content=content)
            return response.json()

        @router.websocket(root_path + "/{path:path}")
        async def ws(
            websocket: WebSocket,
            websocket_permissions=Depends(self._auth.websocket_auth()),
        ) -> None:
            await websocket.accept()
            url = f"http://127.0.0.1:{self._port}" + websocket.url.path
            async with (
                self._client.ws(url) as client_ws,
                create_task_group() as tg,
            ):
                tg.start_soon(self._ws_receive, websocket, client_ws, tg)
                tg.start_soon(self._ws_send, websocket, client_ws, tg)

        self.include_router(router)

    async def _ws_receive(self, server_ws, client_ws, tg):
        try:
            while True:
                message = await server_ws.receive_json()
                await client_ws.send_json(message)
        except Exception:
            tg.cancel_scope.cancel()

    async def _ws_send(self, server_ws, client_ws, tg):
        try:
            while True:
                message = await client_ws.receive_json()
                await server_ws.send_json(message)
        except Exception:
            tg.cancel_scope.cancel()


class _AsyncClient:
    def __init__(self, client: AsyncClient, port: int) -> None:
        self._client = client
        self._url = f"http://127.0.0.1:{port}"
        self._cookies = Cookies()
        self._headers = {}

    async def get(self, url: str, *args: Any, **kwargs: Any) -> Response:
        response = await self._client.get(
            f"{self._url}{url}",
            *args,
            **kwargs,
            cookies=self._cookies,
        )
        self._cookies.update(response.cookies)
        xsrf = response.cookies.get("_xsrf")
        if xsrf:
            self._headers.update({"X-Xsrftoken": xsrf})
        return response

    async def post(self, url: str, *args: Any, **kwargs: Any) -> Response:
        response = await self._client.post(
            f"{self._url}{url}",
            *args,
            **kwargs,
            cookies=self._cookies,
            headers=self._headers,
        )
        self._cookies.update(response.cookies)
        xsrf = response.cookies.get("_xsrf")
        if xsrf:
            self._headers.update({"X-Xsrftoken": xsrf})
        return response

    def ws(self, url: str) -> AsyncGenerator[AsyncWebSocketSession]:
        return aconnect_ws(
            url,
            self._client,
            cookies=self._cookies,
            headers=self._headers,
        )


def get_unused_tcp_port() -> int:
    try:
        sock = socket()
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]
    finally:
        sock.close()
