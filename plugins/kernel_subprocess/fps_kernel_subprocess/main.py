from __future__ import annotations

from fps import Module

from jupyverse_api.environments import Environments
from jupyverse_api.kernel import DefaultKernelFactory

from .kernel_subprocess import KernelSubprocess


class KernelSubprocessModule(Module):
    async def prepare(self) -> None:
        environments = await self.get(Environments)  # type: ignore[type-abstract]

        class _KernelSubprocess(KernelSubprocess):
            def __init__(self, *args, **kwargs):
                super().__init__(*args, environments=environments, **kwargs)

        default_kernel_factory = DefaultKernelFactory(_KernelSubprocess)
        self.put(default_kernel_factory)
