import anyio

from jupyverse_api.contents import HTTPContents

from .contents import _Contents


class _HTTPContents(HTTPContents):
    contents: _Contents
    db_path: anyio.Path
    root_dir: anyio.Path

    def __init__(self, *args, db_path: str = ".fileid.db", root_dir: str = ".", **kwargs):
        self.contents = _Contents(db_path=db_path, root_dir=root_dir)
        super().__init__(*args, **kwargs)
