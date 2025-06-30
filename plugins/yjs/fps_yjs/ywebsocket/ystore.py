from __future__ import annotations

import struct
import tempfile
import time
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Awaitable
from contextlib import AsyncExitStack
from inspect import isawaitable
from pathlib import Path
from typing import Callable, cast

import anyio
from anyio import TASK_STATUS_IGNORED, Event, Lock, create_task_group
from anyio.abc import TaskGroup, TaskStatus
from pycrdt import Decoder, Doc, write_var_uint
from sqlite_anyio import connect
from structlog import BoundLogger, get_logger

from .yutils import get_new_path


class YDocNotFound(Exception):
    pass


class BaseYStore(ABC):
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

    async def __aenter__(self) -> BaseYStore:
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

    async def encode_state_as_update(self, ydoc: Doc) -> None:
        """Store a YDoc state.

        Arguments:
            ydoc: The YDoc from which to store the state.
        """
        update = ydoc.get_update()
        await self.write(update)

    async def apply_updates(self, ydoc: Doc) -> None:
        """Apply all stored updates to the YDoc.

        Arguments:
            ydoc: The YDoc on which to apply the updates.
        """
        async for update, *rest in self.read():  # type: ignore
            ydoc.apply_update(update)


class FileYStore(BaseYStore):
    """A YStore which uses one file per document."""

    path: str
    metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None
    lock: Lock

    def __init__(
        self,
        path: str,
        metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None,
        log: BoundLogger | None = None,
    ) -> None:
        """Initialize the object.

        Arguments:
            path: The file path used to store the updates.
            metadata_callback: An optional callback to call to get the metadata.
            log: An optional logger.
        """
        self.path = path
        self.metadata_callback = metadata_callback
        self.log = log or get_logger()
        self.lock = Lock()

    async def check_version(self) -> int:
        """Check the version of the store format.

        Returns:
            The offset where the data is located in the file.
        """
        if not await anyio.Path(self.path).exists():
            version_mismatch = True
        else:
            version_mismatch = False
            move_file = False
            async with await anyio.open_file(self.path, "rb") as f:
                header = await f.read(8)
                if header == b"VERSION:":
                    version = int(await f.readline())
                    if version == self.version:
                        offset = await f.tell()
                    else:
                        version_mismatch = True
                else:
                    version_mismatch = True
                if version_mismatch:
                    move_file = True
            if move_file:
                new_path = await get_new_path(self.path)
                self.log.warning(
                    "YStore version mismatch, moving file",
                    from_path=self.path,
                    to_path=new_path,
                )
                await anyio.Path(self.path).rename(new_path)
        if version_mismatch:
            async with await anyio.open_file(self.path, "wb") as f:
                version_bytes = f"VERSION:{self.version}\n".encode()
                await f.write(version_bytes)
                offset = len(version_bytes)
        return offset

    async def read(self) -> AsyncIterator[tuple[bytes, bytes, float]]:  # type: ignore
        """Async iterator for reading the store content.

        Returns:
            A tuple of (update, metadata, timestamp) for each update.
        """
        async with self.lock:
            if not await anyio.Path(self.path).exists():
                raise YDocNotFound
            offset = await self.check_version()
            async with await anyio.open_file(self.path, "rb") as f:
                await f.seek(offset)
                data = await f.read()
                if not data:
                    raise YDocNotFound
        i = 0
        for d in Decoder(data).read_messages():
            if i == 0:
                update = d
            elif i == 1:
                metadata = d
            else:
                timestamp = struct.unpack("<d", d)[0]
                yield update, metadata, timestamp
            i = (i + 1) % 3

    async def write(self, data: bytes) -> None:
        """Store an update.

        Arguments:
            data: The update to store.
        """
        parent = Path(self.path).parent
        async with self.lock:
            await anyio.Path(parent).mkdir(parents=True, exist_ok=True)
            await self.check_version()
            async with await anyio.open_file(self.path, "ab") as f:
                data_len = write_var_uint(len(data))
                await f.write(data_len + data)
                metadata = await self.get_metadata()
                metadata_len = write_var_uint(len(metadata))
                await f.write(metadata_len + metadata)
                timestamp = struct.pack("<d", time.time())
                timestamp_len = write_var_uint(len(timestamp))
                await f.write(timestamp_len + timestamp)


class TempFileYStore(FileYStore):
    """A YStore which uses the system's temporary directory.
    Files are writen under a common directory.
    To prefix the directory name (e.g. /tmp/my_prefix_b4whmm7y/):

    ```py
    class PrefixTempFileYStore(TempFileYStore):
        prefix_dir = "my_prefix_"
    ```
    """

    prefix_dir: str | None = None
    base_dir: str | None = None

    def __init__(
        self,
        path: str,
        metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None,
        log: BoundLogger | None = None,
    ):
        """Initialize the object.

        Arguments:
            path: The file path used to store the updates.
            metadata_callback: An optional callback to call to get the metadata.
            log: An optional logger.
        """
        full_path = str(Path(self.get_base_dir()) / path)
        super().__init__(full_path, metadata_callback=metadata_callback, log=log)

    def get_base_dir(self) -> str:
        """Get the base directory where the update file is written.

        Returns:
            The base directory path.
        """
        if self.base_dir is None:
            self.make_directory()
        assert self.base_dir is not None
        return self.base_dir

    def make_directory(self):
        """Create the base directory where the update file is written."""
        type(self).base_dir = tempfile.mkdtemp(prefix=self.prefix_dir)


class SQLiteYStore(BaseYStore):
    """A YStore which uses an SQLite database.
    Unlike file-based YStores, the Y updates of all documents are stored in the same database.

    Subclass to point to your database file:

    ```py
    class MySQLiteYStore(SQLiteYStore):
        db_path = "path/to/my_ystore.db"
    ```
    """

    db_path: str = "ystore.db"
    # Determines the "time to live" for all documents, i.e. how recent the
    # latest update of a document must be before purging document history.
    # Defaults to never purging document history (None).
    document_ttl: int | None = None
    path: str
    lock: Lock
    db_initialized: Event

    def __init__(
        self,
        path: str,
        metadata_callback: Callable[[], Awaitable[bytes] | bytes] | None = None,
        log: BoundLogger | None = None,
    ) -> None:
        """Initialize the object.

        Arguments:
            path: The file path used to store the updates.
            metadata_callback: An optional callback to call to get the metadata.
            log: An optional logger.
        """
        self.path = path
        self.metadata_callback = metadata_callback
        self.log = log or get_logger()
        self.lock = Lock()
        self.db_initialized = Event()

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED):
        """Start the SQLiteYStore.

        Arguments:
            task_status: The status to set when the task has started.
        """
        self._db = await connect(self.db_path)
        await self._init_db()
        await super().start(task_status=task_status)

    async def stop(self) -> None:
        """Stop the store."""
        await self._db.close()
        await super().stop()

    async def _init_db(self):
        create_db = False
        move_db = False
        if not await anyio.Path(self.db_path).exists():
            create_db = True
        else:
            async with self.lock:
                cursor = await self._db.cursor()
                await cursor.execute(
                    "SELECT count(name) FROM sqlite_master WHERE type='table' and name='yupdates'"
                )
                table_exists = (await cursor.fetchone())[0]
                if table_exists:
                    await cursor.execute("pragma user_version")
                    version = (await cursor.fetchone())[0]
                    if version != self.version:
                        move_db = True
                        create_db = True
                else:
                    create_db = True
        if move_db:
            new_path = await get_new_path(self.db_path)
            self.log.warning(
                "YStore version mismatch, moving database",
                from_path=self.db_path,
                to_path=new_path,
            )
            await anyio.Path(self.db_path).rename(new_path)
        if create_db:
            async with self.lock:
                cursor = await self._db.cursor()
                await cursor.execute(
                    "CREATE TABLE yupdates "
                    "(path TEXT NOT NULL, yupdate BLOB, metadata BLOB, timestamp REAL NOT NULL)"
                )
                await cursor.execute(
                    "CREATE INDEX idx_yupdates_path_timestamp ON yupdates (path, timestamp)"
                )
                await cursor.execute(f"PRAGMA user_version = {self.version}")
                await self._db.commit()
        self.db_initialized.set()

    async def read(self) -> AsyncIterator[tuple[bytes, bytes, float]]:  # type: ignore
        """Async iterator for reading the store content.

        Returns:
            A tuple of (update, metadata, timestamp) for each update.
        """
        await self.db_initialized.wait()
        try:
            async with self.lock:
                cursor = await self._db.cursor()
                await cursor.execute(
                    "SELECT yupdate, metadata, timestamp FROM yupdates WHERE path = ?",
                    (self.path,),
                )
                found = False
                for update, metadata, timestamp in await cursor.fetchall():
                    found = True
                    yield update, metadata, timestamp
                if not found:
                    raise YDocNotFound
        except Exception:
            raise YDocNotFound

    async def write(self, data: bytes) -> None:
        """Store an update.

        Arguments:
            data: The update to store.
        """
        await self.db_initialized.wait()
        async with self.lock:
            # first, determine time elapsed since last update
            cursor = await self._db.cursor()
            await cursor.execute(
                "SELECT timestamp FROM yupdates WHERE path = ? ORDER BY timestamp DESC LIMIT 1",
                (self.path,),
            )
            row = await cursor.fetchone()
            diff = (time.time() - row[0]) if row else 0

            if self.document_ttl is not None and diff > self.document_ttl:
                # squash updates
                ydoc: Doc = Doc()
                await cursor.execute("SELECT yupdate FROM yupdates WHERE path = ?", (self.path,))
                for (update,) in await cursor.fetchall():
                    ydoc.apply_update(update)
                # delete history
                await cursor.execute("DELETE FROM yupdates WHERE path = ?", (self.path,))
                # insert squashed updates
                squashed_update = ydoc.get_update()
                metadata = await self.get_metadata()
                await cursor.execute(
                    "INSERT INTO yupdates VALUES (?, ?, ?, ?)",
                    (self.path, squashed_update, metadata, time.time()),
                )

            # finally, write this update to the DB
            metadata = await self.get_metadata()
            await cursor.execute(
                "INSERT INTO yupdates VALUES (?, ?, ?, ?)",
                (self.path, data, metadata, time.time()),
            )
            await self._db.commit()
