import os
import subprocess
import sys
from typing import Any

import pytest
from anyio import fail_after, sleep
from fps import get_root_module, merge_config
from httpx2 import AsyncClient

pytestmark = pytest.mark.skipif(sys.platform == "win32", reason="POSIX PTY")

CONFIG = {
    "jupyverse": {
        "type": "jupyverse",
        "modules": {
            "app": {
                "type": "app",
            },
            "auth": {
                "type": "auth",
                "config": {
                    "mode": "noauth",
                },
            },
            "frontend": {
                "type": "frontend",
            },
            "terminals": {
                "type": "terminals",
            },
        },
    }
}


async def run(websocket: Any, command: str, marker: str) -> str:
    """Run a command in the shell and return what it printed after the marker."""
    await websocket.send_json(["stdin", f"echo {marker}$({command})\r"])
    output = ""
    with fail_after(10):
        while True:
            msg = await websocket.receive_json()
            if msg[0] == "stdout":
                output += msg[1]
                # The echoed command line contains "marker$(", the result does not.
                for line in output.splitlines():
                    if line.startswith(marker) and "$(" not in line:
                        return line[len(marker) :].strip()


def is_alive(pid: int) -> bool:
    # ps rather than /proc, which macOS lacks; a zombie is not alive.
    stat = subprocess.run(["ps", "-o", "stat=", "-p", str(pid)], capture_output=True, text=True)
    return stat.stdout.strip()[:1] not in ("", "Z")


@pytest.mark.anyio
async def test_terminal_outlives_websocket(free_tcp_port: int) -> None:
    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        name = (await http.post(f"{url}/api/terminals")).json()["name"]

        async with http.websocket(f"{url}/terminals/websocket/{name}") as websocket:
            pid = int(await run(websocket, "echo $$", "PID="))

        # The websocket is gone, the shell is not.
        await sleep(0.5)
        assert is_alive(pid)
        terminals = (await http.get(f"{url}/api/terminals")).json()
        assert name in [terminal["name"] for terminal in terminals]

        # A new websocket reaches the same shell.
        async with http.websocket(f"{url}/terminals/websocket/{name}") as websocket:
            assert int(await run(websocket, "echo $$", "PID=")) == pid

        # Deleting the terminal ends the shell.
        response = await http.delete(f"{url}/api/terminals/{name}")
        assert response.status_code == 204
        with fail_after(10):
            while is_alive(pid):
                await sleep(0.1)
        assert (await http.get(f"{url}/api/terminals")).json() == []


@pytest.mark.anyio
async def test_terminal_removed_when_shell_exits(free_tcp_port: int) -> None:
    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        name = (await http.post(f"{url}/api/terminals")).json()["name"]

        async with http.websocket(f"{url}/terminals/websocket/{name}") as websocket:
            await websocket.send_json(["setup", {}])
            await websocket.send_json(["stdin", "exit\r"])
            # The client is told the shell is gone.
            with fail_after(10):
                while (await websocket.receive_json()) != ["disconnect", 1]:
                    pass

        with fail_after(10):
            while (await http.get(f"{url}/api/terminals")).json():
                await sleep(0.1)


@pytest.mark.anyio
async def test_terminals_unlisted_on_stop(free_tcp_port: int) -> None:
    from fps_terminals.routes import TERMINALS

    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        await http.post(f"{url}/api/terminals")
        assert TERMINALS

    assert not TERMINALS


@pytest.mark.anyio
async def test_reap_does_not_block_on_unkillable_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    from fps_terminals import server

    # A shell stuck in uninterruptible I/O: never reaped, even after SIGKILL.
    signals = []
    waitpid_flags = []
    monkeypatch.setattr(server.os, "kill", lambda pid, sig: signals.append(sig))
    monkeypatch.setattr(
        server.os, "waitpid", lambda pid, flags: waitpid_flags.append(flags) or (0, 0)
    )
    monkeypatch.setattr(server, "sleep", lambda delay: sleep(0))
    terminal = object.__new__(server._TerminalServer)
    terminal.pid = 12345

    with fail_after(5):
        await terminal._reap()

    assert signals == [server.signal.SIGKILL]
    assert waitpid_flags and all(flags == os.WNOHANG for flags in waitpid_flags)


@pytest.mark.anyio
async def test_terminal_failure_spares_other_terminals(free_tcp_port: int) -> None:
    from fps_terminals.routes import TERMINALS

    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        failing = (await http.post(f"{url}/api/terminals")).json()["name"]
        other = (await http.post(f"{url}/api/terminals")).json()["name"]

        def on_exit() -> None:
            raise RuntimeError("on_exit failed")

        TERMINALS[failing]["server"].on_exit = on_exit
        async with http.websocket(f"{url}/terminals/websocket/{failing}") as websocket:
            await websocket.send_json(["stdin", "exit\r"])
        with fail_after(10):
            while not TERMINALS[failing]["server"].closed:
                await sleep(0.1)

        async with http.websocket(f"{url}/terminals/websocket/{other}") as websocket:
            assert await run(websocket, "echo ok", "OUT=") == "ok"
        assert (await http.post(f"{url}/api/terminals")).status_code == 200


def test_windows_terminal_quit(monkeypatch: pytest.MonkeyPatch) -> None:
    # winpty is Windows-only: fake it to check the server's bookkeeping.
    class PTY:
        def __init__(self, columns, lines):
            pass

        def spawn(self, command, env):
            pass

    monkeypatch.setitem(sys.modules, "winpty", type(sys)("winpty"))
    monkeypatch.setattr(sys.modules["winpty"], "PTY", PTY, raising=False)
    monkeypatch.delitem(sys.modules, "fps_terminals.win_server", raising=False)
    import fps_terminals
    from fps_terminals import win_server

    # Unload the fake-backed module afterwards.
    monkeypatch.setitem(sys.modules, "fps_terminals.win_server", win_server)
    monkeypatch.setattr(fps_terminals, "win_server", win_server, raising=False)

    exits = []
    terminal = win_server._TerminalServer(None, lambda: exits.append(1))
    websocket = object()
    terminal.websockets.append(websocket)

    # Ends with its last websocket, then DELETE and shutdown are no-ops.
    terminal.quit(websocket)
    terminal.quit()
    terminal.quit()
    assert exits == [1]
    assert not hasattr(terminal, "process")

    # A terminal deleted before any websocket.
    terminal = win_server._TerminalServer(None, lambda: exits.append(2))
    terminal.quit()
    assert exits == [1, 2]


@pytest.mark.anyio
async def test_stop_quits_terminals_that_unlist_themselves(monkeypatch: pytest.MonkeyPatch) -> None:
    from fps_terminals import routes

    # Like the Windows server, whose quit() runs on_exit at once.
    class Server:
        def __init__(self, name: str) -> None:
            self.name = name
            self.quitted = False

        def quit(self) -> None:
            self.quitted = True
            terminals._on_exit(self.name, self)

    monkeypatch.setattr(routes, "TERMINALS", {})
    terminals = object.__new__(routes._Terminals)
    terminals.stop_event = routes.Event()
    servers = [Server("1"), Server("2")]
    for server in servers:
        routes.TERMINALS[server.name] = {"info": None, "server": server}

    await terminals.stop()

    assert all(server.quitted for server in servers)
    assert terminals.stop_event.is_set()
    assert routes.TERMINALS == {}


@pytest.mark.anyio
async def test_shell_ignoring_sighup_is_killed_on_stop(free_tcp_port: int) -> None:
    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        name = (await http.post(f"{url}/api/terminals")).json()["name"]
        async with http.websocket(f"{url}/terminals/websocket/{name}") as websocket:
            await websocket.send_json(["stdin", "trap '' HUP\r"])
            pid = int(await run(websocket, "echo $$", "PID="))
            # Unlike bash, sleep does not exit when the terminal goes away.
            await websocket.send_json(["stdin", "exec sleep 300\r"])
            await sleep(0.5)

    # The server stopped before the reaping delay was up.
    try:
        with fail_after(5):
            while is_alive(pid):
                await sleep(0.1)
    finally:
        if is_alive(pid):
            os.kill(pid, 9)


@pytest.mark.anyio
async def test_terminal_unlisted_when_quit_fails(free_tcp_port: int) -> None:
    from fps_terminals.routes import TERMINALS

    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        name = (await http.post(f"{url}/api/terminals")).json()["name"]
        server = TERMINALS[name]["server"]
        quit = server.quit

        def failing_quit(websocket: Any = None) -> None:
            quit(websocket)
            if websocket is None:
                raise RuntimeError("quit failed")

        server.quit = failing_quit
        async with http.websocket(f"{url}/terminals/websocket/{name}") as websocket:
            await websocket.send_json(["stdin", "exit\r"])

        with fail_after(10):
            while (await http.get(f"{url}/api/terminals")).json():
                await sleep(0.1)
