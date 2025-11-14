from __future__ import annotations

from abc import ABC, abstractmethod

from anyio import TASK_STATUS_IGNORED, Event, create_memory_object_stream
from anyio.abc import TaskStatus
from anyio.streams.memory import MemoryObjectReceiveStream
from anyio.streams.stapled import StapledObjectStream


class Kernel(ABC):
    def __init__(self) -> None:
        self.key = "0"
        self.wait_for_ready = False
        self.started = Event()

        self._to_shell_send_stream, self._to_shell_receive_stream = create_memory_object_stream[
            list[bytes]
        ]()
        self._from_shell_send_stream, self._from_shell_receive_stream = create_memory_object_stream[
            list[bytes]
        ]()
        self._to_control_send_stream, self._to_control_receive_stream = create_memory_object_stream[
            list[bytes]
        ]()
        self._from_control_send_stream, self._from_control_receive_stream = (
            create_memory_object_stream[list[bytes]]()
        )
        self._to_stdin_send_stream, self._to_stdin_receive_stream = create_memory_object_stream[
            list[bytes]
        ]()
        self._from_stdin_send_stream, self._from_stdin_receive_stream = create_memory_object_stream[
            list[bytes]
        ]()
        self._from_iopub_send_stream, self._from_iopub_receive_stream = create_memory_object_stream[
            list[bytes]
        ](max_buffer_size=float("inf"))
        self._shell_stream = StapledObjectStream(
            self._to_shell_send_stream, self._from_shell_receive_stream
        )
        self._control_stream = StapledObjectStream(
            self._to_control_send_stream, self._from_control_receive_stream
        )
        self._stdin_stream = StapledObjectStream(
            self._to_stdin_send_stream, self._from_stdin_receive_stream
        )

    @abstractmethod
    async def start(
        self,
        *,
        task_status: TaskStatus[None] = TASK_STATUS_IGNORED,
    ) -> None: ...

    @abstractmethod
    async def stop(self) -> None: ...

    @abstractmethod
    async def interrupt(self) -> None: ...

    @property
    def shell_stream(self) -> StapledObjectStream[list[bytes]]:
        return self._shell_stream

    @property
    def control_stream(self) -> StapledObjectStream[list[bytes]]:
        return self._control_stream

    @property
    def stdin_stream(self) -> StapledObjectStream[list[bytes]]:
        return self._stdin_stream

    @property
    def iopub_stream(self) -> MemoryObjectReceiveStream[list[bytes]]:
        return self._from_iopub_receive_stream


class KernelFactory:
    def __init__(self, kernel_factory: type[Kernel]) -> None:
        self._kernel_factory = kernel_factory

    def __call__(self, *args, **kwargs) -> Kernel:
        return self._kernel_factory(*args, **kwargs)


class DefaultKernelFactory(KernelFactory):
    pass
