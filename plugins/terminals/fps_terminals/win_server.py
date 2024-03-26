import os
from functools import partial

from anyio import to_thread
from winpty import PTY  # type: ignore

from jupyverse_api.terminals import TerminalServer


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

        async with create_task_group() as self.task_group:
            self.task_group.start_soon(self.send_data)
            self.task_group.start_soon(self.recv_data)

    async def send_data(self):
        while True:
            try:
                data = await to_thread.run_sync(partial(self.process.read, blocking=True))
            except Exception:
                await self.websocket.send_json(["disconnect", 1])
                return
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
            self.task_group.cancel_scope.cancel()
            del self.process
