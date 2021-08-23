import os
import asyncio
import pty
import shlex
import termios
import struct
import fcntl

from fastapi import WebSocketDisconnect


def open_terminal(command="bash", columns=80, lines=24):
    pid, fd = pty.fork()
    if pid == 0:
        argv = shlex.split(command)
        env = dict(
            TERM="linux", LC_ALL="en_GB.UTF-8", COLUMNS=str(columns), LINES=str(lines)
        )
        os.execvpe(argv[0], argv, env)
    return fd


class TerminalServer:
    def __init__(self):
        self.fd = open_terminal()
        self.p_out = os.fdopen(self.fd, "w+b", 0)
        self.websockets = []

    async def serve(self, websocket):
        self.websocket = websocket
        self.websockets.append(websocket)
        self.event = asyncio.Event()
        self.loop = asyncio.get_event_loop()

        task = asyncio.create_task(self.send_data())

        def on_output():
            try:
                self.data_or_disconnect = self.p_out.read(65536).decode()
                self.event.set()
            except Exception:
                self.loop.remove_reader(self.p_out)
                self.data_or_disconnect = None
                self.event.set()

        self.loop.add_reader(self.p_out, on_output)
        await websocket.send_json(["setup", {}])
        try:
            while True:
                msg = await websocket.receive_json()
                if msg[0] == "stdin":
                    self.p_out.write(msg[1].encode())
                elif msg[0] == "set_size":
                    winsize = struct.pack("HH", msg[1], msg[2])
                    fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        except WebSocketDisconnect:
            task.cancel()

    async def send_data(self):
        while True:
            await self.event.wait()
            self.event.clear()
            if self.data_or_disconnect is None:
                await self.websocket.send_json(["disconnect", 1])
            else:
                for websocket in self.websockets:
                    await websocket.send_json(["stdout", self.data_or_disconnect])

    def quit(self, websocket):
        self.websockets.remove(websocket)
        if not self.websockets:
            os.close(self.fd)
