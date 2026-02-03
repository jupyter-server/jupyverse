from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from inspect import isawaitable
from typing import TYPE_CHECKING, cast

if TYPE_CHECKING:
    from pycrdt import Doc


class YStore(ABC):
    metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None
    version = 2

    @abstractmethod
    def __init__(
        self, path: str, metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None
    ): ...

    @abstractmethod
    async def __aenter__(self) -> "YStore": ...

    @abstractmethod
    async def __aexit__(self, exc_type, exc_value, exc_tb) -> bool | None: ...

    @abstractmethod
    async def write(self, data: bytes) -> None: ...

    @abstractmethod
    async def read(self) -> AsyncIterator[tuple[bytes, bytes]]: ...

    async def get_metadata(self) -> bytes:
        """
        Returns:
            The metadata.
        """
        if self.metadata_callback is None:
            return b""

        metadata = self.metadata_callback()
        if isawaitable(metadata):
            metadata = await metadata
        metadata = cast(bytes, metadata)
        return metadata

    async def encode_state_as_update(self, ydoc: "Doc") -> None:
        """Store a YDoc state.

        Arguments:
            ydoc: The YDoc from which to store the state.
        """
        update = ydoc.get_update()
        await self.write(update)

    async def apply_updates(self, ydoc: "Doc") -> None:
        """Apply all stored updates to the YDoc.

        Arguments:
            ydoc: The YDoc on which to apply the updates.
        """
        async for update, *rest in self.read():  # type: ignore
            ydoc.apply_update(update)


class YDocNotFound(Exception):
    pass


class YStoreFactory:
    def __init__(self, ystore_factory: type[YStore]) -> None:
        self._ystore_factory = ystore_factory

    def __call__(self, *args, **kwargs) -> YStore:
        return self._ystore_factory(*args, **kwargs)
