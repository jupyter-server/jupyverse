import asyncio
from pathlib import Path
from typing import Callable, Dict, List, Optional
from uuid import uuid4

import aiosqlite
from aiopath import AsyncPath  # type: ignore
from watchfiles import Change, awatch


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


class FileIdManager:

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
            apath = AsyncPath(path)
            if not await apath.exists():
                return None

            idx = uuid4().hex
            mtime = (await apath.stat()).st_mtime
            await db.execute("INSERT INTO fileids VALUES (?, ?, ?)", (idx, path, mtime))
            await db.commit()
            return idx

    async def watch_files(self):
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "CREATE TABLE IF NOT EXISTS fileids "
                "(id TEXT PRIMARY KEY, path TEXT NOT NULL, mtime REAL NOT NULL)"
            )
            await db.commit()

        async with aiosqlite.connect(self.db_path) as db:
            async for path in AsyncPath().rglob("*"):
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
                    changed_path = str(Path(changed_path).relative_to(Path().absolute()))

                    if change == Change.deleted:
                        async with db.execute(
                            "SELECT * FROM fileids WHERE path = ?", (changed_path,)
                        ) as cursor:
                            async for _ in cursor:
                                break
                            else:
                                # path is not indexed, ignore
                                continue
                        # path is indexed
                        await maybe_rename(db, changed_path, deleted_paths, added_paths, False)
                    elif change == Change.added:
                        await maybe_rename(db, changed_path, added_paths, deleted_paths, True)

                for path in deleted_paths + added_paths:
                    await db.execute("DELETE FROM fileids WHERE path = ?", (path,))
                await db.commit()

                for change in changes:
                    changed_path = change[1]
                    # get relative path
                    changed_path = str(Path(changed_path).relative_to(Path().absolute()))
                    for watcher in self.watchers.get(changed_path, []):
                        watcher.notify(change)

    def watch(self, path: str) -> Watcher:
        watcher = Watcher(path)
        if path not in self.watchers:
            self.watchers[path] = watchers = []  # type: ignore
        watchers.append(watcher)
        return watcher


async def get_mtime(path, db) -> Optional[float]:
    if db:
        async with db.execute("SELECT * FROM fileids WHERE path = ?", (path,)) as cursor:
            async for _, _, mtime in cursor:
                return mtime
            # deleted file is not in database, shouldn't happen
            return None
    try:
        mtime = (await AsyncPath(path).stat()).st_mtime
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
            await db.execute("UPDATE fileids SET path = REPLACE(path, ?, ?)", (path1, path2))
            other_paths.remove(other_path)
            return
    changed_paths.append(changed_path)


FILE_ID_MANAGER: Optional[FileIdManager] = None


def get_file_id_manager() -> FileIdManager:
    global FILE_ID_MANAGER
    if FILE_ID_MANAGER is None:
        FILE_ID_MANAGER = FileIdManager()
    assert FILE_ID_MANAGER is not None
    return FILE_ID_MANAGER


def get_watch() -> Callable[[str], Watcher]:
    return get_file_id_manager().watch
