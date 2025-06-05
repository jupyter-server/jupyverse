from __future__ import annotations

import logging
import sqlite3
from uuid import uuid4

import structlog
from anyio import Event, Lock, Path
from sqlite_anyio import connect
from watchfiles import Change, awatch

from jupyverse_api.file_id import FileId

logger = structlog.get_logger()
watchfiles_logger = logging.getLogger("watchfiles")
watchfiles_logger.setLevel(logging.WARNING)


class Watcher:
    def __init__(self, path: str) -> None:
        self.path = path
        self._event = Event()

    def __aiter__(self):
        return self

    async def __anext__(self):
        await self._event.wait()
        self._event = Event()
        return self._change

    def notify(self, change):
        self._change = change
        self._event.set()


class _FileId(FileId):
    db_path: str
    initialized: Event
    watchers: dict[str, list[Watcher]]
    lock: Lock

    def __init__(self, db_path: str = ".fileid.db"):
        self.db_path = db_path
        self.initialized = Event()
        self.watchers = {}
        self.stop_event = Event()
        self.lock = Lock()

    async def start(self) -> None:
        self._db = await connect(self.db_path)
        try:
            await self.watch_files()
        except sqlite3.ProgrammingError:
            pass

    async def stop(self) -> None:
        await self._db.close()
        self.stop_event.set()

    async def get_id(self, path: str) -> str | None:
        await self.initialized.wait()
        async with self.lock:
            cursor = await self._db.cursor()
            await cursor.execute("SELECT id FROM fileids WHERE path = ?", (path,))
            for (idx,) in await cursor.fetchall():
                return idx
            return None

    async def get_path(self, idx: str) -> str | None:
        await self.initialized.wait()
        async with self.lock:
            cursor = await self._db.cursor()
            await cursor.execute("SELECT path FROM fileids WHERE id = ?", (idx,))
            for (path,) in await cursor.fetchall():
                return path
            return None

    async def index(self, path: str) -> str | None:
        await self.initialized.wait()
        async with self.lock:
            apath = Path(path)
            if not await apath.exists():
                return None

            idx = uuid4().hex
            mtime = (await apath.stat()).st_mtime
            cursor = await self._db.cursor()
            await cursor.execute("INSERT INTO fileids VALUES (?, ?, ?)", (idx, path, mtime))
            await self._db.commit()
            return idx

    async def watch_files(self):
        async with self.lock:
            cursor = await self._db.cursor()
            await cursor.execute("DROP TABLE IF EXISTS fileids")
            await cursor.execute(
                "CREATE TABLE fileids "
                "(id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, mtime REAL NOT NULL)"
            )
            await self._db.commit()

        # index files
        async with self.lock:
            cursor = await self._db.cursor()
            async for path in Path().rglob("*"):
                idx = uuid4().hex
                try:
                    mtime = (await path.stat()).st_mtime
                except FileNotFoundError:
                    pass
                else:
                    await cursor.execute(
                        "INSERT INTO fileids VALUES (?, ?, ?)", (idx, str(path), mtime)
                    )
            await self._db.commit()
            self.initialized.set()

        async for changes in awatch(".", stop_event=self.stop_event):
            async with self.lock:
                deleted_paths = set()
                added_paths = set()
                cursor = await self._db.cursor()
                for change, changed_path in changes:
                    # get relative path
                    changed_path = Path(changed_path).relative_to(await Path().absolute())
                    changed_path_str = str(changed_path)

                    if change == Change.deleted:
                        logger.debug("File was deleted", path=changed_path_str)
                        await cursor.execute(
                            "SELECT COUNT(*) FROM fileids WHERE path = ?", (changed_path_str,)
                        )
                        if not (await cursor.fetchone())[0]:
                            # path is not indexed, ignore
                            logger.debug(
                                "File is not indexed, ignoring",
                                path=changed_path_str,
                            )
                            continue
                        # path is indexed
                        await maybe_rename(
                            self._db, changed_path_str, deleted_paths, added_paths, False
                        )
                    elif change == Change.added:
                        logger.debug("File was added", path=changed_path_str)
                        await maybe_rename(
                            self._db, changed_path_str, added_paths, deleted_paths, True
                        )
                    elif change == Change.modified:
                        logger.debug("File was modified", path=changed_path_str)
                        if changed_path_str == self.db_path:
                            continue
                        await cursor.execute(
                            "SELECT COUNT(*) FROM fileids WHERE path = ?", (changed_path_str,)
                        )
                        if not (await cursor.fetchone())[0]:
                            # path is not indexed, ignore
                            logger.debug(
                                "File is not indexed, ignoring",
                                path=changed_path_str,
                            )
                            continue
                        mtime = (await changed_path.stat()).st_mtime
                        await cursor.execute(
                            "UPDATE fileids SET mtime = ? WHERE path = ?",
                            (mtime, changed_path_str),
                        )

                for path in deleted_paths - added_paths:
                    logger.debug("Unindexing file", path=path)
                    await cursor.execute("DELETE FROM fileids WHERE path = ?", (path,))
                await self._db.commit()

            for change in changes:
                changed_path = change[1]
                # get relative path
                relative_changed_path = str(Path(changed_path).relative_to(await Path().absolute()))
                relative_change = (change[0], relative_changed_path)
                for watcher in self.watchers.get(relative_changed_path, []):
                    watcher.notify(relative_change)

    def watch(self, path: str) -> Watcher:
        watcher = Watcher(path)
        self.watchers.setdefault(path, []).append(watcher)
        return watcher

    def unwatch(self, path: str, watcher: Watcher):
        self.watchers[path].remove(watcher)


async def get_mtime(path, db) -> float | None:
    if db:
        cursor = await db.cursor()
        await cursor.execute("SELECT mtime FROM fileids WHERE path = ?", (path,))
        for (mtime,) in await cursor.fetchall():
            return mtime
        # deleted file is not in database, shouldn't happen
        return None
    try:
        mtime = (await Path(path).stat()).st_mtime
    except FileNotFoundError:
        return None
    return mtime


async def maybe_rename(
    db, changed_path: str, changed_paths: set[str], other_paths: set[str], is_added_path: bool
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
            logger.debug("File was renamed", from_path=path1, to_path=path2)
            cursor = await db.cursor()
            await cursor.execute("UPDATE fileids SET path = ? WHERE path = ?", (path2, path1))
            other_paths.remove(other_path)
            return
    changed_paths.add(changed_path)
