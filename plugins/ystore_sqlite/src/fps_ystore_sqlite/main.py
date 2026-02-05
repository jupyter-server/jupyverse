from functools import partial

from fps import Module
from jupyverse_api.ystore import YStoreFactory
from pydantic import Field

from jupyverse_api import Config

from .ystore import SQLiteYStore


class YStoreSQLiteModule(Module):
    def __init__(self, name: str, **kwargs):
        super().__init__(name)
        self.config = YStoreSQLiteConfig(**kwargs)

    async def prepare(self) -> None:
        sqlite_ystore_factory = YStoreFactory(partial(SQLiteYStore, db_path=self.config.db_path))  # type: ignore[arg-type]
        self.put(sqlite_ystore_factory)


class YStoreSQLiteConfig(Config):
    db_path: str = Field(
        description=("The path to the SQLite database."),
        default=".jupyter_ystore.db",
    )
