import importlib

from fastapi import FastAPI
import uvicorn  # type: ignore


class Jupyverse:
    def __init__(self, host: str = "127.0.0.1", port: int = 8000, routers: str = ""):
        self.host = host
        self.port = port
        self.app = FastAPI()
        self.routers = [
            importlib.import_module(router).init(self)  # type: ignore
            for router in routers.split(",")
        ]

        uvicorn.run(self.app, host=host, port=port)
