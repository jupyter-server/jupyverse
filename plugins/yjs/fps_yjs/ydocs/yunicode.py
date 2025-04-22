from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from pycrdt import Awareness, Doc, Text

from .ybasedoc import YBaseDoc


class YUnicode(YBaseDoc):
    def __init__(self, ydoc: Doc | None = None, awareness: Awareness | None = None):
        super().__init__(ydoc,awareness)
        self._ysource = self._ydoc.get("source", type=Text)
        self.undo_manager.expand_scope(self._ysource)

    @property
    def version(self) -> str:
        return "1.0.0"

    def get(self) -> str:
        return str(self._ysource)

    def set(self, value: str) -> None:
        with self._ydoc.transaction():
            # clear document
            self._ysource.clear()
            # initialize document
            if value:
                self._ysource += value

    def observe(self, callback: Callable[[str, Any], None]) -> None:
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(partial(callback, "state"))
        self._subscriptions[self._ysource] = self._ysource.observe(partial(callback, "source"))
