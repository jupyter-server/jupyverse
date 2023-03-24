from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import APIRouter
from jupyverse_api import Router


class Lab(Router, ABC):
    @abstractmethod
    def init_router(
        self, router: APIRouter, redirect_after_root: str
    ) -> Tuple[Path, List[Dict[str, Any]]]:
        ...

    @abstractmethod
    def get_federated_extensions(self, extensions_dir: Path) -> Tuple[List, List]:
        ...
