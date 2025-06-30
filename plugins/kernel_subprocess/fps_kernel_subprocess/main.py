from __future__ import annotations

from fps import Module

from jupyverse_api.kernel import KernelSubprocessFactory

from .kernel_subprocess import KernelSubprocess


class KernelSubprocessModule(Module):
    async def prepare(self) -> None:
        kernel_subprocess_factory = KernelSubprocessFactory(KernelSubprocess)
        self.put(kernel_subprocess_factory)
