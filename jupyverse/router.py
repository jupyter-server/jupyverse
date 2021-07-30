import sys
from pathlib import Path

from fastapi import APIRouter


class JAPIRouter(APIRouter):
    def __init__(self):
        super().__init__()
        self.prefix_dir = Path(sys.prefix)
