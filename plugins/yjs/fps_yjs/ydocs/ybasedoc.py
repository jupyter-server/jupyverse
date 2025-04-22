from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from pycrdt import Awareness, Doc, Map, Subscription, UndoManager


class YBaseDoc(ABC):
    _ydoc: Doc
    _ystate: Map
    _subscriptions: dict[Any, Subscription]
    _undo_manager: UndoManager

    def __init__(self, ydoc: Doc | None = None, awareness: Awareness | None = None):
        if ydoc is None:
            self._ydoc = Doc()
        else:
            self._ydoc = ydoc
        self.awareness = awareness

        self._ystate = self._ydoc.get("state", type=Map)
        self._subscriptions = {}
        self._undo_manager = UndoManager(doc=self._ydoc, capture_timeout_millis=0)

    @property
    @abstractmethod
    def version(self) -> str:
        ...

    @property
    def undo_manager(self) -> UndoManager:
        return self._undo_manager

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
    def hash(self) -> str | None:
        return self._ystate.get("hash")

    @hash.setter
    def hash(self, value: str) -> None:
        self._ystate["hash"] = value

    @property
    def path(self) -> str | None:
        return self._ystate.get("path")

    @path.setter
    def path(self, value: str) -> None:
        self._ystate["path"] = value

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
