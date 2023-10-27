import base64
from functools import partial
from typing import Any, Callable, Optional, Union

from pycrdt import Doc, Map

from .ybasedoc import YBaseDoc


class YBlob(YBaseDoc):
    """
    Extends :class:`YBaseDoc`, and represents a blob document.
    It is currently encoded as base64 because of:
    https://github.com/y-crdt/ypy/issues/108#issuecomment-1377055465
    The Y document can be set from bytes or from str, in which case it is assumed to be encoded as
    base64.
    """

    def __init__(self, ydoc: Optional[Doc] = None):
        super().__init__(ydoc)
        self._ysource = Map()
        self._ydoc["source"] = self._ysource

    @property
    def version(self) -> str:
        return "1.0.0"

    def get(self) -> bytes:
        return base64.b64decode(self._ysource["base64"].encode())

    def set(self, value: Union[bytes, str]) -> None:
        if isinstance(value, bytes):
            value = base64.b64encode(value).decode()
        self._ysource["base64"] = value

    def observe(self, callback: Callable[[str, Any], None]) -> None:
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(partial(callback, "state"))
        self._subscriptions[self._ysource] = self._ysource.observe(partial(callback, "source"))
