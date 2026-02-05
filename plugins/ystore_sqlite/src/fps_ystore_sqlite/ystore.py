import sys
import time
from collections.abc import AsyncIterator

import anyio
from anyio import Event, Lock
from jupyverse_api.ystore import YDocNotFound, YStore
from sqlite_anyio import connect

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class SQLiteYStore(YStore):
    def __init__(
        self,
        path: str,
        db_path: str = "ystore.db",
    ) -> None:
        self._path = path
        self._db_path = db_path
        self._lock = Lock()
        self._db_initialized = Event()

    async def __aenter__(self) -> Self:
        self._db = await connect(self._db_path)
        await self._init_db()
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb) -> bool | None:
        await self._db.close()
        return None

    async def _init_db(self):
        create_db = False
        move_db = False
        if not await anyio.Path(self._db_path).exists():
            create_db = True
        else:
            async with self._lock:
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
            new_path = await get_new_path(self._db_path)
            await anyio.Path(self._db_path).rename(new_path)
        if create_db:
            async with self._lock:
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
        self._db_initialized.set()

    async def read(self) -> AsyncIterator[tuple[bytes, bytes, float]]:  # type: ignore
        await self._db_initialized.wait()
        try:
            async with self._lock:
                cursor = await self._db.cursor()
                await cursor.execute(
                    "SELECT yupdate, metadata, timestamp FROM yupdates WHERE path = ?",
                    (self._path,),
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
        await self._db_initialized.wait()
        async with self._lock:
            cursor = await self._db.cursor()
            metadata = b""
            await cursor.execute(
                "INSERT INTO yupdates VALUES (?, ?, ?, ?)",
                (self._path, data, metadata, time.time()),
            )
            await self._db.commit()


async def get_new_path(path: str) -> str:
    _path = anyio.Path(path)
    ext = _path.suffix
    path_noext = _path.with_suffix("")
    i = 1
    dir_list = [p async for p in _path.parent.iterdir()]
    while True:
        new_path = f"{path_noext}({i}){ext}"
        if new_path not in dir_list:
            break
        i += 1
    return str(new_path)
