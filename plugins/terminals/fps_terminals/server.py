import asyncio
import fcntl
import os
import pty
import shlex
import struct
import termios

from jupyverse_api.terminals import TerminalServer


def open_terminal(command="bash", columns=80, lines=24):
    pid, fd = pty.fork()
    if pid == 0:
        argv = shlex.split(command)
        env = os.environ.copy()
        env.update(TERM="linux", COLUMNS=str(columns), LINES=str(lines))
        os.execvpe(argv[0], argv, env)
    return fd


class _TerminalServer(TerminalServer):
    def __init__(self):
        self.fd = open_terminal()
        self.p_out = os.fdopen(self.fd, "w+b", 0)
        self.loop = asyncio.get_event_loop()
        self.data_from_terminal = asyncio.Queue()
        self.websockets = []

        def on_output():
            try:
                data = self.p_out.read(65536).decode()
            except Exception:
                self.data_from_terminal.put_nowait(None)
            else:
                self.data_from_terminal.put_nowait(data)

        self.loop.add_reader(self.p_out, on_output)

    async def serve(self, websocket, permissions, terminals, name):
        self.websocket = websocket
        self.websockets.append(websocket)

        task = asyncio.create_task(self.send_data(terminals, name))  # noqa: F841

        await websocket.send_json(["setup", {}])
        can_execute = permissions is None or "execute" in permissions.get("terminals", [])
        try:
            while True:
                msg = await websocket.receive_json()
                if can_execute:
                    if msg[0] == "stdin":
                        self.p_out.write(msg[1].encode())
                    elif msg[0] == "set_size":
                        winsize = struct.pack("HH", msg[1], msg[2])
                        fcntl.ioctl(self.fd, termios.TIOCSWINSZ, winsize)
        except Exception:
            if websocket in self.websockets:
                self.websockets.remove(websocket)

    async def send_data(self, terminals, name):
        while True:
            data = await self.data_from_terminal.get()
            if data is None:
                await self.exit(terminals, name)
                return

            for websocket in self.websockets:
                await websocket.send_json(["stdout", data])

    async def exit(self, terminals, name):
        for websocket in self.websockets:
            try:
                await websocket.send_json(["disconnect", 1])
            except Exception:
                pass
        self.websockets.clear()
        try:
            self.loop.remove_reader(self.p_out)
        except Exception:
            pass
        del terminals[name]
