import os
from functools import partial

from anyio import create_task_group, to_thread
from fastapi import WebSocketDisconnect
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

    async def serve(self, websocket, permissions) -> None:
        self.websocket = websocket
        self.permissions = permissions
        self.websockets.append(websocket)

        await websocket.send_json(["setup", {}])

        async with create_task_group() as tg:
            self.task_group = tg
            tg.start_soon(self.send_data)
            tg.start_soon(self.recv_data)

    async def stop(self) -> None:
        self.task_group.cancel_scope.cancel()

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
        can_execute = self.permissions is None or "execute" in self.permissions.get("terminals", [])
        try:
            while True:
                msg = await self.websocket.receive_json()
                if can_execute:
                    if msg[0] == "stdin":
                        self.process.write(msg[1])
                    elif msg[0] == "set_size":
                        self.process.set_size(msg[2], msg[1])
        except WebSocketDisconnect:
            self.quit(self.websocket)
            self.task_group.cancel_scope.cancel()

    def quit(self, websocket):
        self.websockets.remove(websocket)
        if not self.websockets:
            self.task_group.cancel_scope.cancel()
            del self.process
