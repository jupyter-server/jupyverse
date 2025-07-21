from __future__ import annotations

from fps import Module

from jupyverse_api.kernel import DefaultKernelFactory

from .kernel_web_worker import KernelWebWorker


class KernelWebWorkerModule(Module):
    async def prepare(self) -> None:
        default_kernel_factory = DefaultKernelFactory(KernelWebWorker)
        self.put(default_kernel_factory)
