from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from pycrdt import Awareness, Doc, Map

from .ybasedoc import YBaseDoc


class YBlob(YBaseDoc):
    _ysource: Map

    def __init__(self, ydoc: Doc | None = None, awareness: Awareness | None = None):
        super().__init__(ydoc,awareness)
        self._ysource = self._ydoc.get("source", type=Map)
        self.undo_manager.expand_scope(self._ysource)

    @property
    def version(self) -> str:
        return "2.0.0"

    def get(self) -> bytes:
        return self._ysource.get("bytes", b"")

    def set(self, value: bytes | str) -> None:
        self._ysource["bytes"] = value

    def observe(self, callback: Callable[[str, Any], None]) -> None:
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(partial(callback, "state"))
        self._subscriptions[self._ysource] = self._ysource.observe(partial(callback, "source"))
