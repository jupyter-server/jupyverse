import asyncio
import logging
from typing import Dict, List, Optional
from uuid import uuid4

import aiosqlite
from anyio import Path
from fps.logging import get_configured_logger  # type: ignore
from watchfiles import Change, awatch

watchfiles_logger = get_configured_logger("watchfiles.main")
watchfiles_logger.setLevel(logging.CRITICAL)
logger = get_configured_logger("contents")


class Watcher:
    def __init__(self, path: str) -> None:
        self.path = path
        self._event = asyncio.Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._event.wait()
        self._event.clear()
        return self._change

    def notify(self, change):
        self._change = change
        self._event.set()


class Singleton(type):
    _instances: Dict = {}

    def __call__(cls, *args, **kwargs):
        if cls not in cls._instances:
            cls._instances[cls] = super(Singleton, cls).__call__(*args, **kwargs)
        return cls._instances[cls]


class FileIdManager(metaclass=Singleton):

    db_path: str
    initialized: asyncio.Event
    watchers: Dict[str, List[Watcher]]

    def __init__(self, db_path: str = "fileid.db"):
        self.db_path = db_path
        self.initialized = asyncio.Event()
        self.watchers = {}
        asyncio.create_task(self.watch_files())

    async def get_id(self, path: str) -> Optional[str]:
        await self.initialized.wait()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT id FROM fileids WHERE path = ?", (path,)) as cursor:
                async for idx, in cursor:
                    return idx
                return None

    async def get_path(self, idx: str) -> Optional[str]:
        await self.initialized.wait()
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute("SELECT path FROM fileids WHERE id = ?", (idx,)) as cursor:
                async for path, in cursor:
                    return path
                return None

    async def index(self, path: str) -> Optional[str]:
        await self.initialized.wait()
        async with aiosqlite.connect(self.db_path) as db:
            apath = Path(path)
            if not await apath.exists():
                return None

            idx = uuid4().hex
            mtime = (await apath.stat()).st_mtime
            await db.execute("INSERT INTO fileids VALUES (?, ?, ?)", (idx, path, mtime))
            await db.commit()
            return idx

    async def watch_files(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("DROP TABLE IF EXISTS fileids")
            await db.execute(
                "CREATE TABLE fileids "
                "(id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, mtime REAL NOT NULL)"
            )
            await db.commit()

        # index files
        async with aiosqlite.connect(self.db_path) as db:
            async for path in Path().rglob("*"):
                idx = uuid4().hex
                mtime = (await path.stat()).st_mtime
                await db.execute("INSERT INTO fileids VALUES (?, ?, ?)", (idx, str(path), mtime))
            await db.commit()
            self.initialized.set()

            async for changes in awatch("."):
                deleted_paths = []
                added_paths = []
                for change, changed_path in changes:
                    # get relative path
                    changed_path = Path(changed_path).relative_to(await Path().absolute())
                    changed_path_str = str(changed_path)

                    if change == Change.deleted:
                        logger.debug("File %s was deleted", changed_path_str)
                        async with db.execute(
                            "SELECT COUNT(*) FROM fileids WHERE path = ?", (changed_path_str,)
                        ) as cursor:
                            if not (await cursor.fetchone())[0]:
                                # path is not indexed, ignore
                                logger.debug("File %s is not indexed, ignoring", changed_path_str)
                                continue
                        # path is indexed
                        await maybe_rename(db, changed_path_str, deleted_paths, added_paths, False)
                    elif change == Change.added:
                        logger.debug("File %s was added", changed_path_str)
                        await maybe_rename(db, changed_path_str, added_paths, deleted_paths, True)
                    elif change == Change.modified:
                        logger.debug("File %s was modified", changed_path_str)
                        if changed_path_str == self.db_path:
                            continue
                        async with db.execute(
                            "SELECT COUNT(*) FROM fileids WHERE path = ?", (changed_path_str,)
                        ) as cursor:
                            if not (await cursor.fetchone())[0]:
                                # path is not indexed, ignore
                                logger.debug("File %s is not indexed, ignoring", changed_path_str)
                                continue
                        mtime = (await changed_path.stat()).st_mtime
                        await db.execute(
                            "UPDATE fileids SET mtime = ? WHERE path = ?", (mtime, changed_path_str)
                        )

                for path in deleted_paths + added_paths:
                    await db.execute("DELETE FROM fileids WHERE path = ?", (path,))
                await db.commit()

                for change in changes:
                    changed_path = change[1]
                    # get relative path
                    changed_path = str(Path(changed_path).relative_to(await Path().absolute()))
                    for watcher in self.watchers.get(changed_path, []):
                        watcher.notify(change)

    def watch(self, path: str) -> Watcher:
        watcher = Watcher(path)
        if path not in self.watchers:
            self.watchers[path] = []
        self.watchers[path].append(watcher)
        return watcher

    def unwatch(self, path: str, watcher: Watcher):
        self.watchers[path].remove(watcher)


async def get_mtime(path, db) -> Optional[float]:
    if db:
        async with db.execute("SELECT mtime FROM fileids WHERE path = ?", (path,)) as cursor:
            async for mtime, in cursor:
                return mtime
            # deleted file is not in database, shouldn't happen
            return None
    try:
        mtime = (await Path(path).stat()).st_mtime
    except FileNotFoundError:
        return None
    return mtime


async def maybe_rename(
    db, changed_path: str, changed_paths: List[str], other_paths: List[str], is_added_path
) -> None:
    # check if the same file was added/deleted, this would be a rename
    db_or_fs1, db_or_fs2 = db, None
    if is_added_path:
        db_or_fs1, db_or_fs2 = db_or_fs2, db_or_fs1
    mtime1 = await get_mtime(changed_path, db_or_fs1)
    if mtime1 is None:
        return
    for other_path in other_paths:
        mtime2 = await get_mtime(other_path, db_or_fs2)
        if mtime1 == mtime2:
            # same files, according to modification times
            path1, path2 = changed_path, other_path
            if is_added_path:
                path1, path2 = path2, path1
            logger.debug("File %s was renamed to %s", path1, path2)
            await db.execute("UPDATE fileids SET path = ? WHERE path = ?", (path2, path1))
            other_paths.remove(other_path)
            return
    changed_paths.append(changed_path)
