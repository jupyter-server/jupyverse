import importlib
import webbrowser
import threading
from fastapi import FastAPI
import uvicorn  # type: ignore


class Jupyverse:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        open_browser: bool = True,
        collaborative: bool = False,
        frontend: str = "jupyter_lab",
        routers: str = "",
    ):
        if frontend:
            routers += f"jupyverse.routers.{frontend},"

        self.host = host
        self.port = port
        self.collaborative = collaborative
        self.app = FastAPI()
        self.routers = [
            importlib.import_module(router).init(self)  # type: ignore
            for router in routers.split(",")
            if router
        ]

        if open_browser:
            threading.Thread(
                target=launch_browser, args=(host, port), daemon=True
            ).start()

    def run(self):
        uvicorn.run(self.app, host=self.host, port=self.port)


def launch_browser(host: str, port: int):
    webbrowser.open_new(f"{host}:{port}")
