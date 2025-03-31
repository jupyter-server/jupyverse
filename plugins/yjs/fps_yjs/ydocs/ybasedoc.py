from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from pycrdt import Doc, Map, Subscription


class YBaseDoc(ABC):
    _ydoc: Doc
    _ystate: Map

    def __init__(self, ydoc: Doc | None = None):
        if ydoc is None:
            self._ydoc = Doc()
        else:
            self._ydoc = ydoc
        self._ystate = Map()
        self._ydoc["state"] = self._ystate
        self._subscriptions: dict[Any, Subscription] = {}

    @property
    @abstractmethod
    def version(self) -> str:
        ...

    @property
    def ystate(self) -> Map:
        return self._ystate

    @property
    def ydoc(self) -> Doc:
        return self._ydoc

    @property
    def source(self) -> Any:
        return self.get()

    @source.setter
    def source(self, value: Any):
        return self.set(value)

    @property
    def dirty(self) -> bool | None:
        return self._ystate.get("dirty")

    @dirty.setter
    def dirty(self, value: bool) -> None:
        self._ystate["dirty"] = value

    @property
    def path(self) -> str | None:
        return self._ystate.get("path")

    @path.setter
    def path(self, value: str) -> None:
        self._ystate["path"] = value

    @property
    def file_id(self) -> str | None:
        return self._ystate.get("file_id")

    @file_id.setter
    def file_id(self, value: str) -> None:
        self._ystate["file_id"] = value

    @abstractmethod
    def get(self) -> Any:
        ...

    @abstractmethod
    def set(self, value: Any) -> None:
        ...

    @abstractmethod
    def observe(self, callback: Callable[[str, Any], None]) -> None:
        ...

    def unobserve(self) -> None:
        for k, v in self._subscriptions.items():
            k.unobserve(v)
        self._subscriptions = {}
