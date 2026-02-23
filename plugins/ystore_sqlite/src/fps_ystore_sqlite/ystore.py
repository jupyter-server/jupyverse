import sys
from collections.abc import AsyncIterator
from time import monotonic

from jupyverse_api.ystore import YDocNotFound, YStore
from sqlite_anyio import Connection

if sys.version_info >= (3, 11):
    from typing import Self
else:
    from typing_extensions import Self


class SQLiteYStore(YStore):
    def __init__(
        self,
        path: str,
        connection: Connection,
    ) -> None:
        self._path = path
        self._db = connection

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, exc_type, exc_value, exc_tb) -> bool | None:
        return None

    async def read(self) -> AsyncIterator[tuple[bytes, bytes, float]]:  # type: ignore
        cursor = await self._db.execute(
            "SELECT yupdate, metadata, timestamp FROM yupdates WHERE path = ?",
            (self._path,),
        )
        found = False
        for update, metadata, timestamp in await cursor.fetchall():
            found = True
            yield update, metadata, timestamp
        if not found:
            raise YDocNotFound

    async def write(self, data: bytes) -> None:
        metadata = b""
        await self._db.execute(
            "INSERT INTO yupdates VALUES (?, ?, ?, ?)",
            (self._path, data, metadata, monotonic()),
        )
        await self._db.commit()
