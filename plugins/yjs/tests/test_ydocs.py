import shutil
import tempfile
from inspect import isawaitable
from pathlib import Path

import pytest
from anyio import sleep
from fastapi.exceptions import HTTPException
from fps_contents.contents import _Contents
from fps_yjs.ydocs.ydrive import YDrive


async def call(func):
    res = func()
    if isawaitable(res):
        res = await res
    return res


async def assert_with_timeout(func, timeout=100):
    dt = 0.1
    tt = 0
    while True:
        await sleep(dt)
        tt += dt
        res = await call(func)
        if res:
            break
        if tt > timeout:
            await sleep(tt - timeout)
            break
        dt *= 2
    assert await call(func)


@pytest.mark.anyio
@pytest.mark.xfail
async def test_ydrive():
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir = Path(tmp_dir)
        (tmp_dir / "file0").write_text(" " * 1)
        (tmp_dir / "file1").write_text(" " * 2)
        (tmp_dir / "dir0").mkdir()
        (tmp_dir / "dir0" / "file2").write_text(" " * 3)
        (tmp_dir / "dir1").mkdir()
        (tmp_dir / "dir1" / "dir2").mkdir()
        (tmp_dir / "dir1" / "dir2" / "file3").write_text(" " * 4)
        (tmp_dir / "dir1" / "dir2" / "file4").write_text(" " * 5)

        contents = _Contents(db_path=str(tmp_dir / ".fileid.db"), root_dir=str(tmp_dir))

        async with YDrive(contents=contents, root_dir=tmp_dir) as ydrive:
            await sleep(0.1)
            await contents.file_id_manager.initialized.wait()

            with pytest.raises(HTTPException) as exc_info:
                await ydrive.ls("doesnt_exist")
            assert str(exc_info.value) == "404: Item not found"

            root_dir = await ydrive.ls()
            assert "file0" in root_dir
            assert "file1" in root_dir
            assert "dir0" in root_dir
            assert "dir1" in root_dir

            dir0 = await ydrive.ls("dir0")
            assert len(dir0) == 1
            assert "file2" in dir0

            dir1 = await ydrive.ls("dir1")
            assert len(dir1) == 1
            assert "dir2" in dir1

            dir2 = await ydrive.ls("dir1/dir2")
            assert len(dir2) == 2
            assert "file3" in dir2
            assert "file4" in dir2
            file3 = await ydrive.ls("dir1/dir2/file3")
            assert not file3["is_dir"]
            assert file3["size"] == 4

            # delete files
            await ydrive.delete("file0")
            async def _(): return "file0" not in await ydrive.ls()
            await assert_with_timeout(_)
            await assert_with_timeout(lambda: not (tmp_dir / "file0").exists())

            await ydrive.delete("dir1/dir2/file3")
            async def _(): return "file3" not in await ydrive.ls()
            await assert_with_timeout(_)
            await assert_with_timeout(lambda: not (tmp_dir / "dir1" / "dir2" / "file3").exists())

            (tmp_dir / "file1").unlink()
            async def _(): return "file1" not in await ydrive.ls()
            await assert_with_timeout(_)

            (tmp_dir / "dir1" / "dir2" / "file4").unlink()
            async def _(): return "file4" not in await ydrive.ls("dir1/dir2")
            await assert_with_timeout(_)

            # create files
            await ydrive.create_directory("new_dir0")
            async def _(): return "new_dir0" in await ydrive.ls()
            await assert_with_timeout(_)
            await assert_with_timeout(lambda: (tmp_dir / "new_dir0").exists())
            await ydrive.create_file("new_dir0/new_file0")
            async def _(): return "new_file0" in await ydrive.ls("new_dir0")
            await assert_with_timeout(_)
            await assert_with_timeout(lambda: (tmp_dir / "new_dir0" / "new_file0").exists())

            (tmp_dir / "dir1" / "dir2" / "file5").write_text("bar")
            async def _(): return "file5" in await ydrive.ls("dir1/dir2")
            await assert_with_timeout(_)

            # copy files
            (tmp_dir / "new_dir0" / "new_file0").write_text("foo")
            await ydrive.copy("new_dir0/new_file0", "new_dir0/new_file1")
            async def _(): return "new_file1" in await ydrive.ls("new_dir0")
            await assert_with_timeout(_)
            async def _(): return (await ydrive.ls("new_dir0"))["new_file1"]["size"] == 3
            await assert_with_timeout(_)
            await assert_with_timeout(lambda: (tmp_dir / "new_dir0" / "new_file0").exists())
            await assert_with_timeout(lambda: (tmp_dir / "new_dir0" / "new_file1").exists())

            # move files
            await ydrive.move("new_dir0/new_file1", "new_dir0/new_file2")
            async def _(): return "new_file1" not in await ydrive.ls("new_dir0")
            await assert_with_timeout(_)
            async def _(): return "new_file2" in await ydrive.ls("new_dir0")
            await assert_with_timeout(_)
            await assert_with_timeout(lambda: not (tmp_dir / "new_dir0" / "new_file1").exists())
            await assert_with_timeout(lambda: (tmp_dir / "new_dir0" / "new_file2").exists())

            shutil.move(str(tmp_dir / "dir1" / "dir2" / "file5"), str(tmp_dir / "dir1"))
            async def _(): return "file5" not in await ydrive.ls("dir1/dir2")
            await assert_with_timeout(_)
            async def _(): return "file5" in await ydrive.ls("dir1")
            await assert_with_timeout(_)
