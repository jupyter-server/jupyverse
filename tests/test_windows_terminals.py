import importlib.util
import sys
from pathlib import Path
from queue import Queue
from threading import Event
from types import ModuleType
from typing import Any

import pytest
from anyio import create_memory_object_stream, create_task_group, fail_after, sleep
from fastapi import WebSocketDisconnect
from fps import get_root_module, merge_config
from httpx2 import AsyncClient


class FakePTY:
    def __init__(self, columns=80, lines=24):
        self.size = (columns, lines)
        self.output = Queue()
        self.read_finished = Event()
        self.io_cancelled = False
        self.alive = True
        self.pid = 12345
        self.writes = []
        self.reads = 0

    def spawn(self, command, env):
        pass

    def read(self, blocking=False):
        assert blocking
        self.reads += 1
        self.read_finished.clear()
        try:
            return self.output.get(timeout=10)
        finally:
            self.read_finished.set()

    def cancel_io(self):
        self.io_cancelled = True
        self.output.put("")

    def isalive(self):
        return self.alive

    def write(self, text):
        self.writes.append(text)

    def set_size(self, columns, lines):
        self.size = (columns, lines)


class WebSocket:
    def __init__(self):
        self.send_stream, self.receive_stream = create_memory_object_stream(10)
        self.messages = []
        self.closed = False
        self.fail_send = False

    async def send_json(self, message):
        if self.fail_send:
            raise RuntimeError("Disconnected")
        self.messages.append(message)

    async def receive_json(self):
        message = await self.receive_stream.receive()
        if message is None:
            raise WebSocketDisconnect()
        return message

    async def close(self):
        self.closed = True
        await self.send_stream.send(None)


@pytest.fixture
def windows_server(monkeypatch):
    import fps_terminals

    # Load a separate copy, without replacing the platform's actual server module.
    dependency = ModuleType("winpty")
    dependency.PTY = FakePTY
    dependency.WinptyError = RuntimeError
    monkeypatch.setitem(sys.modules, "winpty", dependency)
    path = Path(fps_terminals.__file__).with_name("win_server.py")
    spec = importlib.util.spec_from_file_location("test_win_server", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    kills = []

    def kill(pid, signal):
        kills.append(pid)
        for process in processes:
            if process.pid == pid:
                process.alive = False

    processes = []

    def open_terminal():
        process = FakePTY()
        processes.append(process)
        return process

    monkeypatch.setattr(module, "open_terminal", open_terminal)
    monkeypatch.setattr(module.os, "kill", kill)
    return module._TerminalServer, processes, kills


async def wait_for(predicate):
    with fail_after(5):
        while not predicate():
            await sleep(0.01)


@pytest.mark.anyio
async def test_windows_terminal_reconnects_and_shares_output(windows_server):
    server, processes, kills = windows_server
    async with create_task_group() as tasks:
        terminal = server()
        await tasks.start(terminal.run)
        process = processes[0]
        first, second = WebSocket(), WebSocket()
        tasks.start_soon(terminal.serve, first, None)
        tasks.start_soon(terminal.serve, second, None)
        await wait_for(lambda: len(terminal.websockets) == 2)
        await first.send_stream.send(["set_size", 40, 120])
        await second.send_stream.send(["set_size", 30, 150])
        await wait_for(lambda: process.size == (120, 30))
        process.output.put("shared output")
        await wait_for(lambda: ["stdout", "shared output"] in first.messages)
        await wait_for(lambda: ["stdout", "shared output"] in second.messages)
        await second.send_stream.send(None)
        await wait_for(lambda: process.size == (120, 40))
        await first.send_stream.send(None)
        await wait_for(lambda: not terminal.websockets)
        assert not terminal.closed and process.alive
        assert kills == []
        previous_reads = process.reads
        process.output.put("output while disconnected")
        await wait_for(lambda: process.reads > previous_reads and process.output.empty())
        reconnected = WebSocket()
        tasks.start_soon(terminal.serve, reconnected, None)
        await reconnected.send_stream.send(["stdin", "still here"])
        await wait_for(lambda: process.writes == ["still here"])
        process.output.put("new output")
        await wait_for(lambda: ["stdout", "new output"] in reconnected.messages)
        terminal.quit()
        terminal.quit()
        await wait_for(lambda: terminal.process is None and reconnected.closed)
        assert kills == [process.pid]


@pytest.mark.anyio
@pytest.mark.parametrize("ending", ["exit", "delete", "cancel"])
async def test_windows_terminal_cleanup_without_clients(windows_server, ending):
    server, processes, kills = windows_server
    async with create_task_group() as tasks:
        terminal = server()
        await tasks.start(terminal.run)
        process = processes[0]
        await wait_for(lambda: process.reads > 0)
        if ending == "exit":
            process.alive = False
            process.output.put("")
        elif ending == "delete":
            terminal.quit()
        else:
            tasks.cancel_scope.cancel()
        if ending != "cancel":
            await wait_for(lambda: terminal.process is None)
    await wait_for(process.read_finished.is_set)
    assert process.io_cancelled
    assert terminal.closed and terminal.process is None
    assert not process.alive
    assert kills == ([] if ending == "exit" else [process.pid])


@pytest.mark.anyio
async def test_windows_terminal_send_failure_only_detaches_client(windows_server):
    server, processes, _ = windows_server
    async with create_task_group() as tasks:
        terminal = server()
        await tasks.start(terminal.run)
        failed, healthy = WebSocket(), WebSocket()
        tasks.start_soon(terminal.serve, failed, None)
        tasks.start_soon(terminal.serve, healthy, None)
        await wait_for(lambda: len(terminal.websockets) == 2)
        failed.fail_send = True
        processes[0].output.put("output")
        await wait_for(lambda: ["stdout", "output"] in healthy.messages)
        assert failed not in terminal.websockets
        assert not terminal.closed
        await failed.send_stream.send(None)
        terminal.quit()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows PTY")
@pytest.mark.anyio
@pytest.mark.parametrize("ending", ["delete", "exit", "shutdown"])
async def test_native_windows_terminal_persistence(free_tcp_port, monkeypatch, ending):
    from fps_terminals.routes import TERMINALS

    monkeypatch.setenv("COMSPEC", "cmd.exe")
    config = {
        "jupyverse": {
            "type": "jupyverse",
            "modules": {
                "app": {"type": "app"},
                "auth": {"type": "auth", "config": {"mode": "noauth"}},
                "frontend": {"type": "frontend"},
                "terminals": {"type": "terminals"},
            },
        }
    }
    config = merge_config(config, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"

    async def output_contains(websocket: Any, marker: str):
        output = ""
        with fail_after(10):
            while marker not in output:
                message = await websocket.receive_json()
                if message[0] == "stdout":
                    output += message[1]

    async with root_module, AsyncClient() as http:
        name = (await http.post(f"{url}/api/terminals")).json()["name"]
        terminal = TERMINALS[name]["server"]
        process = terminal.process
        path = f"{url}/terminals/websocket/{name}"
        async with http.websocket(path) as websocket:
            await websocket.send_json(["stdin", "set JUPYVERSE_TEST=persistent\r"])
            await websocket.send_json(["stdin", "echo initialized%JUPYVERSE_TEST%\r"])
            await output_contains(websocket, "initializedpersistent")
        await wait_for(lambda: not terminal.websockets)
        assert process.isalive()
        assert name in [entry["name"] for entry in (await http.get(f"{url}/api/terminals")).json()]
        async with http.websocket(path) as websocket:
            assert terminal.process is process
            await websocket.send_json(["stdin", "echo reconnected%JUPYVERSE_TEST%\r"])
            await output_contains(websocket, "reconnectedpersistent")
            if ending == "exit":
                await websocket.send_json(["stdin", "exit\r"])
                with fail_after(10):
                    while await websocket.receive_json() != ["disconnect", 1]:
                        pass
        if ending == "delete":
            assert (await http.delete(f"{url}/api/terminals/{name}")).status_code == 204
        if ending != "shutdown":
            await wait_for(lambda: terminal.closed and name not in TERMINALS)
            await wait_for(lambda: not process.isalive())
    assert terminal.closed and name not in TERMINALS
    await wait_for(lambda: not process.isalive())
