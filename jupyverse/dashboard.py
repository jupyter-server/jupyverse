import asyncio
import atexit
import json
import sys
import subprocess
from typing import List, Optional

from rich.text import Text  # type: ignore
from rich.table import Table  # type: ignore
from textual import events  # type: ignore
from textual.app import App  # type: ignore
from textual.reactive import Reactive  # type: ignore
from textual.widgets import Footer, ScrollView  # type: ignore
from textual.widget import Widget  # type: ignore

FPS: Optional[subprocess.Popen] = None


def stop_fps():
    if FPS is not None:
        FPS.terminate()


atexit.register(stop_fps)


class Dashboard(App):
    """A dashboard for Jupyverse"""

    async def on_load(self, event: events.Load) -> None:
        await self.bind("e", "show_endpoints", "Show endpoints")
        await self.bind("l", "show_log", "Show log")
        await self.bind("q", "quit", "Quit")

    show = Reactive("endpoints")
    body_change = asyncio.Event()
    text = Text()
    table = Table(title="API Summary")

    def action_show_log(self) -> None:
        self.show = "log"

    def action_show_endpoints(self) -> None:
        self.show = "endpoints"

    def watch_show(self, show: str) -> None:
        self.body_change.set()

    async def on_mount(self, event: events.Mount) -> None:

        footer = Footer()
        body = ScrollView(auto_width=True)

        await self.view.dock(footer, edge="bottom")
        await self.view.dock(body)

        async def add_content():
            global FPS
            cmd = ["fps-uvicorn", "--fps.show_endpoints"] + sys.argv[1:]
            FPS = await asyncio.create_subprocess_exec(
                *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            queues = [asyncio.Queue() for i in range(2)]
            asyncio.create_task(get_log(queues))
            asyncio.create_task(self._show_log(queues[0]))
            asyncio.create_task(self._show_endpoints(queues[1]))
            asyncio.create_task(self._change_body(body))

        await self.call_later(add_content)

    async def _change_body(self, body: Widget):
        while True:
            await self.body_change.wait()
            self.body_change.clear()
            if self.show == "endpoints":
                await body.update(self.table)
            elif self.show == "log":
                await body.update(self.text)

    async def _show_endpoints(self, queue: asyncio.Queue):
        endpoint_marker = "ENDPOINT:"
        get_endpoint = False
        endpoints = []
        while True:
            line = await queue.get()
            if endpoint_marker in line:
                get_endpoint = True
            elif get_endpoint:
                break
            if get_endpoint:
                i = line.find(endpoint_marker) + len(endpoint_marker)
                line = line[i:].strip()
                if not line:
                    break
                endpoint = json.loads(line)
                endpoints.append(endpoint)

        self.table.add_column("Path", justify="left", style="cyan", no_wrap=True)
        self.table.add_column("Methods", justify="right", style="green")
        self.table.add_column("Plugin", style="magenta")

        for endpoint in endpoints:
            path = endpoint["path"]
            methods = ", ".join(endpoint["methods"])
            plugin = ", ".join(endpoint["plugin"])
            if "WEBSOCKET" in methods:
                path = f"[cyan on red]{path}[/]"
            self.table.add_row(path, methods, plugin)

        self.body_change.set()

    async def _show_log(self, queue: asyncio.Queue):
        while True:
            line = await queue.get()
            self.text.append(line)
            self.body_change.set()


async def get_log(queues: List[asyncio.Queue]):
    assert FPS is not None
    assert FPS.stderr is not None
    while True:
        line = await FPS.stderr.readline()
        if line:
            line = line.decode()
            for queue in queues:
                await queue.put(line)
        else:
            break
