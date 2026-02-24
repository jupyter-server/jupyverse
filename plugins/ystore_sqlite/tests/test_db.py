from time import time

import pytest
from anyio import create_task_group, wait_all_tasks_blocked
from fps_ystore_sqlite.main import YStoreSQLiteModule
from jupyverse_api.ystore import YDocNotFound, YStoreFactory
from pycrdt import Doc, Text


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
        t0 = time()
        await ystore.write(b"foo")
        t1 = time()

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
        assert set(tmp_path.iterdir()) == {db_path, db_path1}

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

        t0 = time()
        await ystore.write(b"bar")
        t1 = time()

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


@pytest.mark.anyio
async def test_concurrent_accesses(tmp_path):
    db_path = tmp_path / "test.db"
    doc0 = Doc()
    doc1 = Doc()

    async def write_doc_to_store(doc, store, *, task_status):
        async with doc.events(async_transactions=True, max_buffer_size=0) as events:
            task_status.started()
            async for event in events:
                await store.write(event.update)

    async with (
        YStoreSQLiteModule("ystore_sqlite", db_path=str(db_path)) as ystore_sqlite,
        create_task_group() as tg,
    ):
        ystore_factory = await ystore_sqlite.get(YStoreFactory)
        ystore0 = ystore_factory("doc0")
        ystore1 = ystore_factory("doc1")
        await tg.start(write_doc_to_store, doc0, ystore0)
        await tg.start(write_doc_to_store, doc1, ystore1)
        text0 = doc0.get("text0", type=Text)
        text1 = doc1.get("text1", type=Text)
        for i in range(100):
            async with doc0.new_transaction(), doc1.new_transaction():
                text0 += str(i)
                text1 += str(i + 1)
        await wait_all_tasks_blocked()

        _doc0 = Doc()
        _doc1 = Doc()
        await ystore0.apply_updates(_doc0)
        await ystore1.apply_updates(_doc1)

        ref0 = "".join([str(i) for i in range(100)])
        ref1 = "".join([str(i + 1) for i in range(100)])
        _text0 = _doc0.get("text0", type=Text)
        _text1 = _doc1.get("text1", type=Text)
        assert str(_text0) == ref0
        assert str(_text1) == ref1
        tg.cancel_scope.cancel()
