from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AsyncExitStack
from inspect import isawaitable
from typing import TYPE_CHECKING, cast

from anyio import TASK_STATUS_IGNORED, Event, create_task_group
from anyio.abc import TaskGroup, TaskStatus

if TYPE_CHECKING:
    from pycrdt import Doc


class YStore(ABC):
    metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None
    version = 2
    _started: Event | None = None
    _starting: bool = False
    _task_group: TaskGroup | None = None

    @abstractmethod
    def __init__(
        self, path: str, metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None
    ): ...

    @abstractmethod
    async def write(self, data: bytes) -> None: ...

    @abstractmethod
    async def read(self) -> AsyncIterator[tuple[bytes, bytes]]: ...

    @property
    def started(self) -> Event:
        if self._started is None:
            self._started = Event()
        return self._started

    async def __aenter__(self) -> "YStore":
        if self._task_group is not None:
            raise RuntimeError("YStore already running")

        async with AsyncExitStack() as exit_stack:
            tg = create_task_group()
            self._task_group = await exit_stack.enter_async_context(tg)
            self._exit_stack = exit_stack.pop_all()
            await tg.start(self.start)

        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        await self.stop()
        return await self._exit_stack.__aexit__(exc_type, exc_value, exc_tb)

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        """Start the store.

        Arguments:
            task_status: The status to set when the task has started.
        """
        if self._starting:
            return

        self._starting = True

        if self._task_group is not None:
            raise RuntimeError("YStore already running")

        self.started.set()
        self._starting = False
        task_status.started()

    async def stop(self) -> None:
        """Stop the store."""
        if self._task_group is None:
            raise RuntimeError("YStore not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None

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
