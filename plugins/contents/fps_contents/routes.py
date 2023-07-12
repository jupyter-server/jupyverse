import base64
import json
import os
import shutil
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

from anyio import open_file
from fastapi import HTTPException, Response
from jupyverse_api.auth import User
from jupyverse_api.contents import Contents
from jupyverse_api.contents.models import (
    Checkpoint,
    Content,
    CreateContent,
    RenameContent,
    SaveContent,
)
from starlette.requests import Request

from .fileid import FileIdManager


class _Contents(Contents):
    async def create_checkpoint(
        self,
        path,
        user: User,
    ):
        src_path = Path(path)
        dst_path = Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
        try:
            dst_path.parent.mkdir(exist_ok=True)
            shutil.copyfile(src_path, dst_path)
        except Exception:
            # FIXME: return error code?
            return []
        mtime = get_file_modification_time(dst_path)
        return Checkpoint(**{"id": "checkpoint", "last_modified": mtime})

    async def create_content(
        self,
        path: Optional[str],
        request: Request,
        user: User,
    ):
        create_content = CreateContent(**(await request.json()))
        content_path = Path(create_content.path)
        if create_content.type == "notebook":
            available_path = get_available_path(content_path / "Untitled.ipynb")
            async with await open_file(available_path, "w") as f:
                await f.write(
                    json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5})
                )
            src_path = available_path
            dst_path = Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
            try:
                dst_path.parent.mkdir(exist_ok=True)
                shutil.copyfile(src_path, dst_path)
            except Exception:
                # FIXME: return error code?
                pass
        elif create_content.type == "directory":
            name = "Untitled Folder"
            available_path = get_available_path(content_path / name, sep=" ")
            available_path.mkdir(parents=True, exist_ok=True)
        else:
            assert create_content.ext is not None
            available_path = get_available_path(content_path / ("untitled" + create_content.ext))
            open(available_path, "w").close()

        return await self.read_content(available_path, False)

    async def get_root_content(
        self,
        content: int,
        user: User,
    ):
        return await self.read_content("", bool(content))

    async def get_checkpoint(
        self,
        path,
        user: User,
    ):
        src_path = Path(path)
        dst_path = Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
        if not dst_path.exists():
            return []
        mtime = get_file_modification_time(dst_path)
        return [Checkpoint(**{"id": "checkpoint", "last_modified": mtime})]

    async def get_content(
        self,
        path: str,
        content: int,
        user: User,
    ):
        return await self.read_content(path, bool(content))

    async def save_content(
        self,
        path,
        request: Request,
        response: Response,
        user: User,
    ):
        content = SaveContent(**(await request.json()))
        try:
            await self.write_content(content)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Error saving {content.path}")
        return await self.read_content(content.path, False)

    async def delete_content(
        self,
        path,
        user: User,
    ):
        p = Path(path)
        if p.exists():
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def rename_content(
        self,
        path,
        request: Request,
        user: User,
    ):
        rename_content = RenameContent(**(await request.json()))
        Path(path).rename(rename_content.path)
        return await self.read_content(rename_content.path, False)

    async def read_content(
        self, path: Union[str, Path], get_content: bool, file_format: Optional[str] = None
    ) -> Content:
        if isinstance(path, str):
            path = Path(path)
        content: Optional[Union[str, Dict, List[Dict]]] = None
        if get_content:
            if path.is_dir():
                content = [
                    (await self.read_content(subpath, get_content=False)).model_dump()
                    for subpath in path.iterdir()
                    if not subpath.name.startswith(".")
                ]
            elif path.is_file() or path.is_symlink():
                try:
                    async with await open_file(path, mode="rb") as f:
                        content_bytes = await f.read()
                    if file_format == "base64":
                        content = base64.b64encode(content_bytes).decode("ascii")
                    elif file_format == "json":
                        content = json.loads(content_bytes)
                    else:
                        content = content_bytes.decode()
                except Exception:
                    raise HTTPException(status_code=404, detail="Item not found")
        format: Optional[str] = None
        if path.is_dir():
            size = None
            type = "directory"
            format = "json"
            mimetype = None
        elif path.is_file() or path.is_symlink():
            size = get_file_size(path)
            if path.suffix == ".ipynb":
                type = "notebook"
                format = None
                mimetype = None
                if content is not None:
                    nb: dict
                    if file_format == "json":
                        content = cast(Dict, content)
                        nb = content
                    else:
                        content = cast(str, content)
                        nb = json.loads(content)
                    for cell in nb["cells"]:
                        if "metadata" not in cell:
                            cell["metadata"] = {}
                        cell["metadata"].update({"trusted": False})
                    if file_format != "json":
                        content = json.dumps(nb)
            elif path.suffix == ".json":
                type = "json"
                format = "text"
                mimetype = "application/json"
            else:
                type = "file"
                format = None
                mimetype = "text/plain"
        else:
            raise HTTPException(status_code=404, detail="Item not found")

        return Content(
            **{
                "name": path.name,
                "path": path.as_posix(),
                "last_modified": get_file_modification_time(path),
                "created": get_file_creation_time(path),
                "content": content,
                "format": format,
                "mimetype": mimetype,
                "size": size,
                "writable": is_file_writable(path),
                "type": type,
            }
        )

    async def write_content(self, content: Union[SaveContent, Dict]) -> None:
        if not isinstance(content, SaveContent):
            content = SaveContent(**content)
        if content.format == "base64":
            async with await open_file(content.path, "wb") as f:
                content.content = cast(str, content.content)
                content_bytes = content.content.encode("ascii")
                await f.write(content_bytes)
        else:
            async with await open_file(content.path, "wt") as f:
                if content.format == "json":
                    dict_content = cast(Dict, content.content)
                    if content.type == "notebook":
                        # see https://github.com/jupyterlab/jupyterlab/issues/11005
                        if (
                            "metadata" in dict_content
                            and "orig_nbformat" in dict_content["metadata"]
                        ):
                            del dict_content["metadata"]["orig_nbformat"]
                    await f.write(json.dumps(dict_content, indent=2))
                else:
                    content.content = cast(str, content.content)
                    await f.write(content.content)

    @property
    def file_id_manager(self):
        return FileIdManager()


def get_available_path(path: Path, sep: str = "") -> Path:
    directory = path.parent
    name = Path(path.name)
    i = None
    while True:
        if i is None:
            i_str = ""
            i = 1
        else:
            i_str = str(i)
            i += 1
        if i_str:
            i_str = sep + i_str
        available_path = directory / (name.stem + i_str + name.suffix)
        if not available_path.exists():
            return available_path


def get_file_modification_time(path: Path):
    if path.exists():
        return datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z"


def get_file_creation_time(path: Path):
    if path.exists():
        return datetime.utcfromtimestamp(path.stat().st_ctime).isoformat() + "Z"


def get_file_size(path: Path) -> Optional[int]:
    if path.exists():
        return path.stat().st_size
    raise HTTPException(status_code=404, detail="Item not found")


def is_file_writable(path: Path) -> bool:
    if path.exists():
        if path.is_dir():
            # FIXME
            return True
        else:
            return os.access(path, os.W_OK)
    return False
