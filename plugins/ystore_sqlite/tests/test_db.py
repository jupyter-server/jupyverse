from time import monotonic

import pytest
from fps_ystore_sqlite.main import YStoreSQLiteModule
from jupyverse_api.ystore import YDocNotFound, YStoreFactory


@pytest.mark.anyio
async def test_move_db(tmp_path):
    db_path = tmp_path / "test.db"
    db_path1 = tmp_path / "test(1).db"
    db_path1.write_bytes(b"hello")
    backup_db_path = tmp_path / "test(2).db"
    path = "id"

    # create initial database with some content
    async with YStoreSQLiteModule(
        "ystore_sqlite", db_path=str(db_path), version=0
    ) as ystore_sqlite:
        ystore_factory = await ystore_sqlite.get(YStoreFactory)
        ystore = ystore_factory(path)
        t0 = monotonic()
        await ystore.write(b"foo")
        t1 = monotonic()

    # check that the content can be retrieved
    async with YStoreSQLiteModule(
        "ystore_sqlite", db_path=str(db_path), version=0
    ) as ystore_sqlite:
        ystore_factory = await ystore_sqlite.get(YStoreFactory)
        ystore = ystore_factory(path)
        updates = [data async for data in ystore.read()]

        assert len(updates) == 1
        assert len(updates[0]) == 3
        assert updates[0][:2] == (b"foo", b"")
        timestamp = updates[0][2]
        assert t0 < timestamp < t1
        assert list(tmp_path.iterdir()) == [db_path, db_path1]

    # try to connect to database with different storage version
    async with YStoreSQLiteModule(
        "ystore_sqlite", db_path=str(db_path), version=1
    ) as ystore_sqlite:
        ystore_factory = await ystore_sqlite.get(YStoreFactory)
        ystore = ystore_factory(path)
        # check that the initial database was moved
        assert set(tmp_path.iterdir()) == {db_path, db_path1, backup_db_path}

        # check that the new database is empty
        with pytest.raises(YDocNotFound):
            async for data in ystore.read():
                pass

        t0 = monotonic()
        await ystore.write(b"bar")
        t1 = monotonic()

    # check that the content of the backup database can be retrieved
    async with YStoreSQLiteModule(
        "ystore_sqlite", db_path=str(backup_db_path), version=0
    ) as ystore_sqlite:
        ystore_factory = await ystore_sqlite.get(YStoreFactory)
        ystore = ystore_factory(path)
        updates = [data async for data in ystore.read()]
        assert updates == [(b"foo", b"", timestamp)]

    # check that the content of the new database can be retrieved
    async with YStoreSQLiteModule(
        "ystore_sqlite", db_path=str(db_path), version=1
    ) as ystore_sqlite:
        ystore_factory = await ystore_sqlite.get(YStoreFactory)
        ystore = ystore_factory(path)
        updates = [data async for data in ystore.read()]

        assert len(updates) == 1
        assert len(updates[0]) == 3
        assert updates[0][:2] == (b"bar", b"")
        timestamp = updates[0][2]
        assert t0 < timestamp < t1
        assert set(tmp_path.iterdir()) == {db_path, db_path1, backup_db_path}
