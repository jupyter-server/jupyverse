from types import SimpleNamespace

import pytest
from anyio import CancelScope, Event, Lock, create_task_group, fail_after
from fps_kernels.routes import _Kernels


@pytest.mark.anyio
async def test_cancelled_shutdown_clears_kernel_registry():
    stopping = Event()
    blocked = Event()

    class Server:
        async def stop(self):
            stopping.set()
            await blocked.wait()

    manager = object.__new__(_Kernels)
    manager._stop_lock = Lock()
    manager.stop_event = Event()
    manager.kernels = {"old-kernel": {"server": Server(), "driver": None}}
    manager.task_group = SimpleNamespace(cancel_scope=CancelScope())

    with fail_after(5):
        async with create_task_group() as tasks:
            tasks.start_soon(manager.stop)
            await stopping.wait()
            tasks.cancel_scope.cancel()

    assert manager.kernels == {}
    assert manager.stop_event.is_set()
    assert manager.task_group.cancel_scope.cancel_called
    # A second stop must not try to stop cancelled servers again.
    await manager.stop()
