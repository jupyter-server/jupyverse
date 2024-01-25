import fcntl
import os
import pty
import selectors
import shlex
import struct
import termios
from functools import partial

from anyio import create_memory_object_stream, create_task_group, from_thread, to_thread
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

    async def serve(self, websocket, permissions) -> None:
        self.websocket = websocket
        self.permissions = permissions
        self.websockets.append(websocket)

        async with create_task_group() as self.task_group:
            self.recv_stream = ReceiveStream(self.p_out, self.task_group)
            self.send_stream = SendStream(self.p_out)
            self.task_group.start_soon(self.backend_to_frontend)
            self.task_group.start_soon(self.frontend_to_backend)

    async def stop(self) -> None:
        os.write(self.recv_stream.pipeout, b"0")
        self.p_out.close()
        try:
            self.recv_stream.sel.unregister(self.p_out)
        except Exception:
            pass
        self.task_group.cancel_scope.cancel()

    async def backend_to_frontend(self):
        while True:
            data = (await self.recv_stream.receive(65536)).decode()
            for websocket in self.websockets:
                await websocket.send_json(["stdout", data])

    async def frontend_to_backend(self):
        await self.websocket.send_json(["setup", {}])
        can_execute = self.permissions is None or "execute" in self.permissions.get("terminals", [])
        try:
            while True:
                msg = await self.websocket.receive_json()
                if can_execute:
                    if msg[0] == "stdin":
                        await self.send_stream.send(msg[1].encode())
                    elif msg[0] == "set_size":
                        winsize = struct.pack("HH", msg[1], msg[2])
                        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        except WebSocketDisconnect:
            self.quit(self.websocket)
            self.task_group.cancel_scope.cancel()

    def quit(self, websocket):
        try:
            os.write(self.recv_stream.pipeout, b"0")
            self.p_out.close()
            self.recv_stream.sel.unregister(self.p_out)
            self.websockets.remove(websocket)
            if not self.websockets:
                os.close(self.fd)
        except Exception:
            pass


class ReceiveStream(ByteReceiveStream):
    def __init__(self, p_out, task_group):
        self.p_out = p_out
        self.sel = selectors.DefaultSelector()
        self.sel.register(self.p_out, selectors.EVENT_READ, self._read)
        self.pipein, self.pipeout = os.pipe()
        f = os.fdopen(self.pipein, "r+b", 0)

        def cb():
            return True

        self.sel.register(f, selectors.EVENT_READ, cb)
        self.send_stream, self.recv_stream = create_memory_object_stream[bytes](
            max_buffer_size=65536
        )

        def reader():
            while True:
                events = self.sel.select()
                for key, mask in events:
                    callback = key.data
                    if callback():
                        return

        task_group.start_soon(partial(to_thread.run_sync, reader, abandon_on_cancel=True))

    def _read(self) -> bool:
        try:
            data = self.p_out.read(65536)
        except OSError:
            self.sel.unregister(self.p_out)
            return True
        else:
            from_thread.run_sync(self.send_stream.send_nowait, data)
            return False

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
