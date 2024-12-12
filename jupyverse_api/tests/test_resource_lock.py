import pytest
from anyio import create_task_group, sleep

from jupyverse_api import ResourceLock

pytestmark = pytest.mark.anyio


async def do_op(operation, resource_lock, operations):
    op, path = operation
    async with resource_lock(path):
        operations.append(operation + ["start"])
        await sleep(0.1)
        operations.append(operation + ["done"])


async def test_resource_lock():
    resource_lock = ResourceLock()

    # test concurrent accesses to the same resource
    idx = "idx"
    operations = []
    async with create_task_group() as tg:
        tg.start_soon(do_op, [0, idx], resource_lock, operations)
        await sleep(0.01)
        tg.start_soon(do_op, [1, idx], resource_lock, operations)

    assert operations == [
        [0, idx, "start"],
        [0, idx, "done"],
        [1, idx, "start"],
        [1, idx, "done"],
    ]

    # test concurrent accesses to different files
    idx0 = "idx0"
    idx1 = "idx1"
    operations = []
    async with create_task_group() as tg:
        tg.start_soon(do_op, [0, idx0], resource_lock, operations)
        await sleep(0.01)
        tg.start_soon(do_op, [1, idx1], resource_lock, operations)
        await sleep(0.01)
        tg.start_soon(do_op, [2, idx0], resource_lock, operations)
        await sleep(0.01)
        tg.start_soon(do_op, [3, idx1], resource_lock, operations)

    assert operations == [
        [0, idx0, "start"],
        [1, idx1, "start"],
        [0, idx0, "done"],
        [2, idx0, "start"],
        [1, idx1, "done"],
        [3, idx1, "start"],
        [2, idx0, "done"],
        [3, idx1, "done"],
    ]
