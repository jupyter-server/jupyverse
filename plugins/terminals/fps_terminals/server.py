import fcntl
import os
import pty
import shlex
import struct
import termios
from functools import partial

from anyio import (
    Lock,
    create_memory_object_stream,
    create_task_group,
    wait_readable,
)
from anyio.abc import ByteReceiveStream, ByteSendStream
from fastapi import WebSocketDisconnect

from jupyverse_api.terminals import TerminalServer


class _TerminalServer(TerminalServer):
    def __init__(self):
        # FIXME: pass in config
        command = "bash"
        columns = 80
        lines = 24

        pid, fd = pty.fork()
        if pid == 0:
            argv = shlex.split(command)
            env = os.environ.copy()
            env.update(TERM="linux", COLUMNS=str(columns), LINES=str(lines))
            os.execvpe(argv[0], argv, env)
        self.fd = fd
        self.p_out = os.fdopen(self.fd, "w+b", 0)
        self.websockets = []
        self.task_group = None
        self.lock = Lock()

    async def serve(self, websocket, permissions) -> None:
        self.permissions = permissions
        self.websockets.append(websocket)

        await self.lock.acquire()
        if self.task_group is None:
            async with create_task_group() as self.task_group:
                self.lock.release()
                self.recv_stream_from_backend = ReceiveStream(
                    self.p_out, self.task_group, self.quit
                )
                async with create_task_group() as tg:
                    self.send_stream_to_backend = SendStream(self.p_out)
                    tg.start_soon(self.backend_to_frontend)
                    tg.start_soon(partial(self.frontend_to_backend, websocket))
        else:
            self.lock.release()
            async with create_task_group() as tg:
                self.send_stream_to_backend = SendStream(self.p_out)
                tg.start_soon(self.backend_to_frontend)
                tg.start_soon(partial(self.frontend_to_backend, websocket))

    async def backend_to_frontend(self):
        while True:
            data = (await self.recv_stream_from_backend.receive(65536)).decode()
            for websocket in self.websockets:
                await websocket.send_json(["stdout", data])

    async def frontend_to_backend(self, websocket):
        await websocket.send_json(["setup", {}])
        can_execute = self.permissions is None or "execute" in self.permissions.get("terminals", [])
        try:
            while True:
                msg = await websocket.receive_json()
                if can_execute:
                    if msg[0] == "stdin":
                        await self.send_stream_to_backend.send(msg[1].encode())
                    elif msg[0] == "set_size":
                        winsize = struct.pack("HH", msg[1], msg[2])
                        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        except WebSocketDisconnect:
            self.quit(websocket)
            self.task_group.cancel_scope.cancel()

    def quit(self, websocket=None):
        if websocket is None:
            self.websockets.clear()
        elif websocket in self.websockets:
            self.websockets.remove(websocket)
        if not self.websockets:
            try:
                os.close(self.fd)
            except Exception:
                pass
            try:
                self.p_out.close()
            except Exception:
                pass
        self.task_group.cancel_scope.cancel()


class ReceiveStream(ByteReceiveStream):
    def __init__(self, p_out, task_group, quit):
        self.p_out = p_out
        self.task_group = task_group
        self.quit = quit
        self.send_stream, self.recv_stream = create_memory_object_stream[bytes](
            max_buffer_size=65536
        )
        task_group.start_soon(self.read)

    async def read(self):
        while True:
            await wait_readable(self.p_out)
            try:
                data = self.p_out.read(65536)
            except OSError:
                self.quit()
                return
            await self.send_stream.send(data)

    async def receive(self, max_bytes: int = 65536) -> bytes:
        data = await self.recv_stream.receive()
        return data

    async def aclose(self) -> None:
        pass


class SendStream(ByteSendStream):
    def __init__(self, p_out):
        self.p_out = p_out

    async def send(self, item: bytes) -> None:
        self.p_out.write(item)

    async def aclose(self) -> None:
        pass
