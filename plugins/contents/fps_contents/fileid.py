import asyncio
import logging
from typing import Dict, List, Optional, Set
from uuid import uuid4

import aiosqlite
from anyio import Path
from jupyverse_api import Singleton
from watchfiles import Change, awatch

logger = logging.getLogger("contents")


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


class FileIdManager(metaclass=Singleton):
    db_path: str
    initialized: asyncio.Event
    watchers: Dict[str, List[Watcher]]
    lock: asyncio.Lock

    def __init__(self, db_path: str = ".fileid.db"):
        self.db_path = db_path
        self.initialized = asyncio.Event()
        self.watchers = {}
        self.watch_files_task = asyncio.create_task(self.watch_files())
        self.stop_watching_files = asyncio.Event()
        self.stopped_watching_files = asyncio.Event()
        self.lock = asyncio.Lock()

    async def get_id(self, path: str) -> Optional[str]:
        await self.initialized.wait()
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT id FROM fileids WHERE path = ?", (path,)) as cursor:
                    async for idx, in cursor:
                        return idx
                    return None

    async def get_path(self, idx: str) -> Optional[str]:
        await self.initialized.wait()
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                async with db.execute("SELECT path FROM fileids WHERE id = ?", (idx,)) as cursor:
                    async for path, in cursor:
                        return path
                    return None

    async def index(self, path: str) -> Optional[str]:
        await self.initialized.wait()
        async with self.lock:
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
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                await db.execute("DROP TABLE IF EXISTS fileids")
                await db.execute(
                    "CREATE TABLE fileids "
                    "(id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, mtime REAL NOT NULL)"
                )
                await db.commit()

        # index files
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as db:
                async for path in Path().rglob("*"):
                    idx = uuid4().hex
                    mtime = (await path.stat()).st_mtime
                    await db.execute(
                        "INSERT INTO fileids VALUES (?, ?, ?)", (idx, str(path), mtime)
                    )
                await db.commit()
                self.initialized.set()

        async for changes in awatch(".", stop_event=self.stop_watching_files):
            async with self.lock:
                async with aiosqlite.connect(self.db_path) as db:
                    deleted_paths = set()
                    added_paths = set()
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
                                    logger.debug(
                                        "File %s is not indexed, ignoring", changed_path_str
                                    )
                                    continue
                            # path is indexed
                            await maybe_rename(
                                db, changed_path_str, deleted_paths, added_paths, False
                            )
                        elif change == Change.added:
                            logger.debug("File %s was added", changed_path_str)
                            await maybe_rename(
                                db, changed_path_str, added_paths, deleted_paths, True
                            )
                        elif change == Change.modified:
                            logger.debug("File %s was modified", changed_path_str)
                            if changed_path_str == self.db_path:
                                continue
                            async with db.execute(
                                "SELECT COUNT(*) FROM fileids WHERE path = ?", (changed_path_str,)
                            ) as cursor:
                                if not (await cursor.fetchone())[0]:
                                    # path is not indexed, ignore
                                    logger.debug(
                                        "File %s is not indexed, ignoring", changed_path_str
                                    )
                                    continue
                            mtime = (await changed_path.stat()).st_mtime
                            await db.execute(
                                "UPDATE fileids SET mtime = ? WHERE path = ?",
                                (mtime, changed_path_str),
                            )

                    for path in deleted_paths - added_paths:
                        logger.debug("Unindexing file %s ", path)
                        await db.execute("DELETE FROM fileids WHERE path = ?", (path,))
                    await db.commit()

            for change in changes:
                changed_path = change[1]
                # get relative path
                relative_changed_path = str(Path(changed_path).relative_to(await Path().absolute()))
                relative_change = (change[0], relative_changed_path)
                for watcher in self.watchers.get(relative_changed_path, []):
                    watcher.notify(relative_change)

        self.stopped_watching_files.set()

    def watch(self, path: str) -> Watcher:
        watcher = Watcher(path)
        self.watchers.setdefault(path, []).append(watcher)
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
    db, changed_path: str, changed_paths: Set[str], other_paths: Set[str], is_added_path: bool
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
    changed_paths.add(changed_path)
