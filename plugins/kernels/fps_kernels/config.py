from typing import Optional

from jupyverse_api.kernels import KernelsConfig


class _KernelsConfig(KernelsConfig):
    default_kernel: str = "python3"
    connection_path: Optional[str] = None
