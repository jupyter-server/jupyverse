import os
from collections.abc import Callable
from functools import partial
from typing import Any

from anyio import create_task_group, to_thread
from anyio.abc import TaskGroup
from fastapi import WebSocketDisconnect
from jupyverse_terminals import TerminalServer
from winpty import PTY  # type: ignore


def open_terminal(command=None, columns=80, lines=24):
    if command is None:
        command = os.environ.get("COMSPEC") or "cmd.exe"
    env = "\0".join([f"{k}={v}" for k, v in os.environ.items()]) + "\0"
    process = PTY(columns, lines)
    process.spawn(command, env=env)
    return process


class _TerminalServer(TerminalServer):
    # Unlike the POSIX server, the shell ends with its last websocket.
    def __init__(self, task_group: TaskGroup, on_exit: Callable[[], None]) -> None:
        self.process = open_terminal()
        self.websockets: list[Any] = []
        self.on_exit = on_exit
        # The serving websocket's, not the shared one passed in.
        self.task_group: TaskGroup | None = None
        self.closed = False

    async def serve(self, websocket, permissions) -> None:
        if self.closed:
            return
        self.websocket = websocket
        self.permissions = permissions
        self.websockets.append(websocket)

        await websocket.send_json(["setup", {}])

        async with create_task_group() as tg:
            self.task_group = tg
            tg.start_soon(self.send_data)
            tg.start_soon(self.recv_data)

    async def stop(self) -> None:
        if self.task_group is not None:
            self.task_group.cancel_scope.cancel()

    async def send_data(self):
        while True:
            try:
                data = await to_thread.run_sync(partial(self.process.read, blocking=True))
            except Exception:
                await self.websocket.send_json(["disconnect", 1])
                self.quit()
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

    def quit(self, websocket: Any = None) -> None:
        if websocket is None:
            self.websockets.clear()
        elif websocket in self.websockets:
            self.websockets.remove(websocket)
        if self.websockets or self.closed:
            return
        self.closed = True
        if self.task_group is not None:
            self.task_group.cancel_scope.cancel()
        del self.process
        self.on_exit()
