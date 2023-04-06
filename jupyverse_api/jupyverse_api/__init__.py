from typing import Dict

from pydantic import BaseModel, Extra

from .app import App


__version__ = "0.1.2"


class Singleton(type):
    _instances: Dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class Config(BaseModel):
    class Config:
        extra = Extra.forbid


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
