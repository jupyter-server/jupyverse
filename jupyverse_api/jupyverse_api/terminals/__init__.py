from abc import ABC, abstractmethod
from jupyverse_api import Router


class Terminals(Router):
    pass


class TerminalServer(ABC):
    @abstractmethod
    async def serve(self, websocket, permissions):
        ...

    @abstractmethod
    def quit(self, websocket):
        ...
