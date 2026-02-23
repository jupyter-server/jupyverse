from functools import partial

import anyio
from fps import Module
from jupyverse_api.ystore import YStoreFactory
from pydantic import Field
from sqlite_anyio import Connection, connect

from jupyverse_api import Config

from .ystore import SQLiteYStore


class YStoreSQLiteModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = YStoreSQLiteConfig(**kwargs)

    async def prepare(self) -> None:
        connection = await init_db(self.config)
        sqlite_ystore_factory = YStoreFactory(partial(SQLiteYStore, connection=connection))  # type: ignore[arg-type]
        self.add_teardown_callback(connection.close)
        self.put(sqlite_ystore_factory)


class YStoreSQLiteConfig(Config):
    db_path: str = Field(
        description="The path to the SQLite database.",
        default=".jupyter_ystore.db",
    )
    version: int = Field(
        description="The version of the SQLite database.",
        default=SQLiteYStore.version,
    )


async def init_db(config: YStoreSQLiteConfig) -> Connection:
    db = await connect(config.db_path)

    create_db = False
    move_db = False
    if not await anyio.Path(config.db_path).exists():
        create_db = True
    else:
        cursor = await db.cursor()
        await cursor.execute(
            "SELECT count(name) FROM sqlite_master WHERE type='table' and name='yupdates'"
        )
        res = await cursor.fetchone()
        assert res is not None
        table_exists = res[0]
        if table_exists:
            await cursor.execute("pragma user_version")
            res = await cursor.fetchone()
            assert res is not None
            version = res[0]
            if version != config.version:
                move_db = True
                create_db = True
        else:
            create_db = True
    if move_db:
        new_path = await get_new_path(config.db_path)
        await anyio.Path(config.db_path).rename(new_path)
        await db.close()
        db = await connect(config.db_path)
    if create_db:
        cursor = await db.cursor()
        await cursor.execute(
            "CREATE TABLE yupdates "
            "(path TEXT NOT NULL, yupdate BLOB, metadata BLOB, timestamp REAL NOT NULL)"
        )
        await cursor.execute(
            "CREATE INDEX idx_yupdates_path_timestamp ON yupdates (path, timestamp)"
        )
        await cursor.execute(f"PRAGMA user_version = {config.version}")
        await db.commit()
    return db


async def get_new_path(path: str) -> str:
    _path = anyio.Path(path)
    ext = _path.suffix
    path_noext = _path.with_suffix("")
    i = 1
    dir_list = [str(p) async for p in _path.parent.iterdir()]
    while True:
        new_path = f"{path_noext}({i}){ext}"
        if new_path not in dir_list:
            break
        i += 1
    return str(new_path)
