import importlib.metadata
from typing import Any

from anyio import Event
from pydantic import BaseModel

from .app import App

try:
    __version__ = importlib.metadata.version("jupyverse_api")
except importlib.metadata.PackageNotFoundError:
    __version__ = "unknown"


class Singleton(type):
    _instances: dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(BaseModel):
    model_config = {"extra": "forbid"}


class Router:
    _app: App

    def __init__(
        self,
        app: App,
    ) -> None:
        self._app = app

    @property
    def _type(self):
        return self.__class__.__name__

    def include_router(self, router, **kwargs):
        self._app._include_router(router, self._type, **kwargs)

    def mount(self, path: str, *args, **kwargs) -> None:
        self._app._mount(path, self._type, *args, **kwargs)

    def add_middleware(self, middleware, *args, **kwargs) -> None:
        self._app.add_middleware(middleware, *args, **kwargs)


class ResourceLock:
    """ResourceLock ensures that accesses cannot be done concurrently on the same resource."""

    _locks: dict[Any, Event]

    def __init__(self):
        self._locks = {}

    def __call__(self, idx: Any):
        return _ResourceLock(idx, self._locks)


class _ResourceLock:
    _idx: Any
    _locks: dict[Any, Event]
    _lock: Event

    def __init__(self, idx: Any, locks: dict[Any, Event]):
        self._idx = idx
        self._locks = locks

    async def __aenter__(self):
        while True:
            if self._idx not in self._locks:
                break
            await self._locks[self._idx].wait()
        self._locks[self._idx] = self._lock = Event()

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        self._lock.set()
        del self._locks[self._idx]
