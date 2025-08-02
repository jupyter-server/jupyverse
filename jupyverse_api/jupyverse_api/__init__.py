import importlib.metadata

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
