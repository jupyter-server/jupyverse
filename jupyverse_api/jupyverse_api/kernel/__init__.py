from __future__ import annotations

from abc import ABC, abstractmethod


class Kernel(ABC):
    @abstractmethod
    async def start(self) -> None:
        ...

    @abstractmethod
    async def stop(self) -> None:
        ...

    @abstractmethod
    async def interrupt(self) -> None:
        ...


class KernelFactory:
    def __init__(self, kernel_factory: type[Kernel]) -> None:
        self._kernel_factory = kernel_factory

    def __call__(self, *args, **kwargs) -> Kernel:
        return self._kernel_factory(*args, **kwargs)


class KernelSubprocessFactory(KernelFactory):
    pass
