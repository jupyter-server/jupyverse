import time
from collections.abc import AsyncIterator, Awaitable, Callable
from pathlib import Path

import anyio
from anyio import TASK_STATUS_IGNORED, Event, Lock
from anyio.abc import TaskStatus
from jupyverse_api.ystore import YDocNotFound, YStore
from pycrdt import Doc
from sqlite_anyio import connect
from structlog import BoundLogger, get_logger


class SQLiteYStore(YStore):
    """A YStore which uses an SQLite database.
    Unlike file-based YStores, the Y updates of all documents are stored in the same database.
    """

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
        db_path: str = "ystore.db",
    ) -> None:
        """Initialize the object.

        Arguments:
            path: The file path used to store the updates.
            metadata_callback: An optional callback to call to get the metadata.
            log: An optional logger.
            db_path: The path to the database file.
        """
        self.path = path
        self.metadata_callback = metadata_callback
        self.log = log or get_logger()
        self.db_path = db_path
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


async def get_new_path(path: str) -> str:
    p = Path(path)
    ext = p.suffix
    p_noext = p.with_suffix("")
    i = 1
    dir_list = [p async for p in anyio.Path().iterdir()]
    while True:
        new_path = f"{p_noext}({i}){ext}"
        if new_path not in dir_list:
            break
        i += 1
    return str(new_path)
