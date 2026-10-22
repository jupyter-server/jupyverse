import os
import subprocess
import sys
from typing import Any

import pytest
from anyio import CancelScope, fail_after, sleep
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
async def test_terminal_uses_smallest_connected_dimensions(free_tcp_port: int) -> None:
    from fps_terminals.routes import TERMINALS

    config = merge_config(CONFIG, {"jupyverse": {"config": {"port": free_tcp_port}}})
    root_module = get_root_module(config)
    root_module._global_start_timeout = 10
    url = f"http://127.0.0.1:{free_tcp_port}"
    async with root_module, AsyncClient() as http:
        name = (await http.post(f"{url}/api/terminals")).json()["name"]
        path = f"{url}/terminals/websocket/{name}"
        async with http.websocket(path) as first:
            await first.send_json(["set_size", 40, 120])
            assert await run(first, "stty size", "SIZE0=") == "40 120"

            async with http.websocket(path) as second:
                # Unreported sizes do not impose an arbitrary default.
                assert await run(first, "stty size", "SIZE1=") == "40 120"
                await second.send_json(["set_size", 30, 150])
                assert await run(second, "stty size", "SIZE2=") == "30 120"
                # Each dimension is minimized independently, regardless of who resized last.
                await first.send_json(["set_size", 50, 100])
                assert await run(first, "stty size", "SIZE3=") == "30 100"
                await second.send_json(["set_size", 60, 90])
                assert await run(second, "stty size", "SIZE4=") == "50 90"
                # A hidden or zero-sized client must not shrink the PTY to zero.
                await second.send_json(["set_size", 0, 0])
                assert await run(second, "stty size", "SIZE5=") == "50 90"

            with fail_after(10):
                while len(TERMINALS[name]["server"].sizes) != 1:
                    await sleep(0.01)
            assert await run(first, "stty size", "SIZE6=") == "50 100"

        with fail_after(10):
            while TERMINALS[name]["server"].sizes:
                await sleep(0.01)
        async with http.websocket(path) as reconnected:
            assert await run(reconnected, "stty size", "SIZE7=") == "50 100"
            await reconnected.send_json(["set_size", 45, 130])
            assert await run(reconnected, "stty size", "SIZE8=") == "45 130"


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
async def test_cancelled_reap_collects_child() -> None:
    from fps_terminals import server

    # Use a real child: checking whether it is alive would also accept a zombie.
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(300)"])
    terminal = object.__new__(server._TerminalServer)
    terminal.pid = child.pid
    try:
        with CancelScope() as scope:
            scope.cancel()
            await terminal._reap()

        # ECHILD proves _reap() collected it, rather than just sending SIGKILL.
        with pytest.raises(ChildProcessError):
            os.waitpid(child.pid, os.WNOHANG)
    finally:
        if child.poll() is None:
            child.kill()
        child.wait()


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
