import importlib
from typing import List

from fastapi import FastAPI
import uvicorn


class Japiter:
    def __init__(
        self, host: str = "127.0.0.1", port: int = 8000, routers: List[str] = []
    ):
        self.host = host
        self.port = port
        self.app = FastAPI()

        for router in routers:
            mod = importlib.import_module(router)
            mod.init(self)

        uvicorn.run(self.app, host=host, port=port)
