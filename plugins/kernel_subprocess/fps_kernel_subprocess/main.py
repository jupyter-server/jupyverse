from __future__ import annotations

from fps import Module

from jupyverse_api.kernel import DefaultKernelFactory

from .kernel_subprocess import KernelSubprocess


class KernelSubprocessModule(Module):
    async def prepare(self) -> None:
        default_kernel_factory = DefaultKernelFactory(KernelSubprocess)
        self.put(default_kernel_factory, DefaultKernelFactory)
