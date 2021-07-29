import importlib
import webbrowser
import threading
from typing import Optional

from fastapi import FastAPI
import uvicorn  # type: ignore


class Jupyverse:
    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 8000,
        open_browser: Optional[bool] = True,
        routers: str = "",
    ):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.routers = [
            importlib.import_module(router).init(self)  # type: ignore
            for router in routers.split(",")
        ]

        if open_browser:
            threading.Thread(
                target=launch_browser, args=(host, port), daemon=True
            ).start()

    def run(self):
        uvicorn.run(self.app, host=self.host, port=self.port)


def launch_browser(host: str, port: int):
    webbrowser.open_new(f"{host}:{port}")
