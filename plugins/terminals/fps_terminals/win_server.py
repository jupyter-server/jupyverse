import asyncio
import os

from jupyverse_api.terminals import TerminalServer
from winpty import PTY  # type: ignore


def open_terminal(command="C:\\Windows\\System32\\cmd.exe", columns=80, lines=24):
    env = "\0".join([f"{k}={v}" for k, v in os.environ.items()]) + "\0"
    process = PTY(columns, lines)
    process.spawn(command, env=env)
    return process


class _TerminalServer(TerminalServer):
    def __init__(self):
        self.process = open_terminal()
        self.websockets = []

    async def serve(self, websocket):
        self.websocket = websocket
        self.websockets.append(websocket)

        await websocket.send_json(["setup", {}])

        self.send_task = asyncio.create_task(self.send_data())
        self.recv_task = asyncio.create_task(self.recv_data())

        await asyncio.gather(self.send_task, self.recv_task)

    async def send_data(self):
        while True:
            try:
                data = self.process.read(blocking=False)
            except Exception:
                await self.websocket.send_json(["disconnect", 1])
                return
            if not data:
                await asyncio.sleep(0.1)
            else:
                for websocket in self.websockets:
                    await websocket.send_json(["stdout", data])

    async def recv_data(self):
        while True:
            try:
                msg = await self.websocket.receive_json()
            except Exception:
                return
            if msg[0] == "stdin":
                self.process.write(msg[1])
            elif msg[0] == "set_size":
                self.process.set_size(msg[2], msg[1])

    def quit(self, websocket):
        self.websockets.remove(websocket)
        if not self.websockets:
            self.send_task.cancel()
            self.recv_task.cancel()
            del self.process
