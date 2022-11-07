import os
from pathlib import Path

import pytest
from utils import clear_content_values, create_content, sort_content_by_name


@pytest.mark.parametrize("auth_mode", ("noauth",))
def test_tree(client, tmp_path):
    prev_dir = os.getcwd()
    os.chdir(tmp_path)
    dname = Path(".")
    expected = []
    # write some files with different size
    for size in range(7, 13):
        fname = f"file_size_{size}"
        with (dname / fname).open("w") as f:
            f.write("-" * size)
        expected.append(
            create_content(
                content=None,
                type="file",
                size=size,
                mimetype="text/plain",
                name=fname,
                path=(dname / fname).as_posix(),
                format=None,
            )
        )
    # write some directories
    for i in range(3):
        sub_dname = f"directory_{i}"
        (dname / sub_dname).mkdir()
        expected.append(
            create_content(
                content=None,
                type="directory",
                size=None,
                mimetype=None,
                name=sub_dname,
                path=(dname / sub_dname).as_posix(),
                format="json",
            )
        )
    expected = create_content(
        content=expected,
        type="directory",
        size=None,
        mimetype=None,
        name="",
        path=dname.as_posix(),
        format="json",
    )
    response = client.get("/api/contents", params={"content": 1})
    actual = response.json()
    # ignore modification and creation times
    clear_content_values(actual, keys=["created", "last_modified"])
    # ensure content names are ordered the same way
    sort_content_by_name(actual)
    sort_content_by_name(expected)
    assert actual == expected
    os.chdir(prev_dir)
