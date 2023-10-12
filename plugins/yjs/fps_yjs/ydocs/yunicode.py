from functools import partial
from typing import Any, Callable, Optional

from pycrdt import Doc, Text

from .ybasedoc import YBaseDoc


class YUnicode(YBaseDoc):
    def __init__(self, ydoc: Optional[Doc] = None):
        super().__init__(ydoc)
        self._ysource = Text()
        self._ydoc["source"] = self._ysource

    @property
    def version(self) -> str:
        return "1.0.0"

    def get(self) -> str:
        return str(self._ysource)

    def set(self, value: str) -> None:
        with self._ydoc.transaction():
            # clear document
            del self._ysource[:]
            # initialize document
            if value:
                self._ysource += value

    def observe(self, callback: Callable[[str, Any], None]) -> None:
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(partial(callback, "state"))
        self._subscriptions[self._ysource] = self._ysource.observe(partial(callback, "source"))
