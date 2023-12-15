import asyncio
import base64
import json
import os
import shutil
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

import anyio
from fastapi import HTTPException, Response

from jupyverse_api.auth import User
from jupyverse_api.contents import Contents
from jupyverse_api.contents.models import (
    Checkpoint,
    Content,
    CopyContent,
    CreateContent,
    RenameContent,
    SaveContent,
)

from .fileid import FileIdManager


class _Contents(Contents):
    def __init__(self, db_path: str = ".fileid.db", root_dir: str = "."):
        self.db_path = anyio.Path(db_path)
        self.root_dir = anyio.Path(root_dir)
        self._root_dir_task = asyncio.create_task(self._resolve_root_dir())

    async def _resolve_root_dir(self):
        self.root_dir = await self.root_dir.resolve()

    async def create_checkpoint(
        self,
        path,
        user: User,
    ):
        await self._root_dir_task
        src_path = self.root_dir / path
        dst_path = self.root_dir / ".ipynb_checkpoints" / \
            f"{src_path.stem}-checkpoint{src_path.suffix}"
        try:
            await dst_path.parent.mkdir(exist_ok=True)
            await anyio.to_thread.run_sync(shutil.copyfile, src_path, dst_path)
        except Exception:
            # FIXME: return error code?
            return []
        mtime = await get_file_modification_time(dst_path)
        return Checkpoint(**{"id": "checkpoint", "last_modified": mtime})

    async def create_file(
        self,
        path: str,
    ) -> None:
        await self._root_dir_task
        content_path = self.root_dir / path
        await content_path.write_text("")

    async def create_directory(
        self,
        path: str,
    ) -> None:
        await self._root_dir_task
        content_path = self.root_dir / path
        await content_path.mkdir(parents=True, exist_ok=True)

    async def copy_content(
        self,
        from_path: str,
        to_path: str,
    ):
        _from_path = self.root_dir / from_path
        _to_path = self.root_dir / to_path
        if await _from_path.is_dir():
            await anyio.to_thread.run_sync(shutil.copytree, _from_path, _to_path)
        else:
            await anyio.to_thread.run_sync(shutil.copyfile, _from_path, _to_path)

    async def move_content(
        self,
        from_path: str,
        to_path: str,
    ):
        _from_path = self.root_dir / from_path
        _to_path = self.root_dir / to_path
        await anyio.to_thread.run_sync(shutil.move, _from_path, _to_path)

    async def create_content(
        self,
        path: Optional[str],
        create_content: Union[CreateContent, CopyContent],
        user: User,
    ):
        await self._root_dir_task
        if isinstance(create_content, CopyContent):
            copy_from = Path(create_content.copy_from)
            assert path is not None
            path_ = Path(path)
            if path_.is_absolute():
                path_ = path_.relative_to(path_.root)
            copy_to = self.root_dir / path_ / copy_from.name
            available_path = await get_available_path(copy_to)
            relative_available_path = str(available_path.relative_to(self.root_dir))
            await self.copy_content(str(copy_from), relative_available_path)
            return await self.read_content(relative_available_path, False)

        assert create_content.path is not None
        content_path = self.root_dir / create_content.path
        if create_content.type == "notebook":
            available_path = await get_available_path(content_path / "Untitled.ipynb")
            await available_path.write_text(
                json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5})
            )
            src_path = available_path
            dst_path = self.root_dir / ".ipynb_checkpoints" / \
                f"{src_path.stem}-checkpoint{src_path.suffix}"
            try:
                await dst_path.parent.mkdir(exist_ok=True)
                await anyio.to_thread.run_sync(shutil.copyfile, src_path, dst_path)
            except Exception:
                # FIXME: return error code?
                pass
        elif create_content.type == "directory":
            name = "Untitled Folder"
            available_path = await get_available_path(content_path / name, sep=" ")
            await available_path.mkdir(parents=True, exist_ok=True)
        else:
            assert create_content.ext is not None
            available_path = await get_available_path(
                content_path / ("untitled" + create_content.ext)
            )
            await available_path.write_text("")

        return await self.read_content(str(available_path.relative_to(self.root_dir)), False)

    async def get_root_content(
        self,
        content: int,
        user: User,
    ):
        return await self.read_content("", bool(content))

    async def get_checkpoint(
        self,
        path: str,
        user: User,
    ):
        await self._root_dir_task
        src_path = self.root_dir / path
        dst_path = self.root_dir / ".ipynb_checkpoints" / \
            f"{src_path.stem}-checkpoint{src_path.suffix}"
        if not await dst_path.exists():
            return []
        mtime = await get_file_modification_time(dst_path)
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
        path: str,
        content: SaveContent,
        user: User,
    ):
        try:
            await self.write_content(content)
        except Exception:
            raise HTTPException(status_code=404, detail=f"Error saving {content.path}")
        return await self.read_content(content.path, False)

    async def delete_content(
        self,
        path: str,
        user: User,
    ):
        await self._root_dir_task
        p = self.root_dir / path
        if await p.exists():
            if await p.is_dir():
                await anyio.to_thread.run_sync(shutil.rmtree, p)
            else:
                await p.unlink()
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def rename_content(
        self,
        path: str,
        rename_content: RenameContent,
        user: User,
    ):
        await self._root_dir_task
        await (self.root_dir / path).rename(self.root_dir / rename_content.path)
        return await self.read_content(rename_content.path, False)

    async def read_content(
        self, path: Union[str, Path], get_content: bool, file_format: Optional[str] = None
    ) -> Content:
        await self._root_dir_task
        apath = self.root_dir / path
        apath = await apath.resolve()
        content: Optional[Union[str, Dict, List[Dict]]] = None
        if get_content:
            if await apath.is_dir():
                content = [
                    (
                        await self.read_content(
                            Path(subpath.relative_to(self.root_dir)),
                            get_content=False,
                        )
                    ).model_dump()
                    async for subpath in apath.iterdir()
                    if not subpath.name.startswith(".")
                ]
            elif await apath.is_file() or await apath.is_symlink():
                try:
                    content_bytes = await apath.read_bytes()
                    if file_format == "base64":
                        content = base64.b64encode(content_bytes).decode("ascii")
                    elif file_format == "json":
                        content = json.loads(content_bytes)
                    else:
                        content = content_bytes.decode()
                except Exception:
                    raise HTTPException(status_code=404, detail="Item not found")
        format: Optional[str] = None
        if await apath.is_dir():
            size = None
            type = "directory"
            format = "json"
            mimetype = None
        elif await apath.is_file() or await apath.is_symlink():
            size = await get_file_size(apath)
            if apath.suffix == ".ipynb":
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
                        if cell["cell_type"] == "code":
                            cell_source = cell["source"]
                            if not isinstance(cell_source, str):
                                cell["source"] = "".join(cell_source)
                    if file_format != "json":
                        content = json.dumps(nb)
            elif apath.suffix == ".json":
                type = "json"
                format = "text"
                mimetype = "application/json"
            else:
                type = "file"
                format = None
                mimetype = "text/plain"
        else:
            raise HTTPException(status_code=404, detail="Item not found")

        rel_path = apath.relative_to(self.root_dir)
        return Content(
            **{
                "name": rel_path.name,
                "path": rel_path.as_posix(),
                "last_modified": await get_file_modification_time(apath),
                "created": await get_file_creation_time(apath),
                "content": content,
                "format": format,
                "mimetype": mimetype,
                "size": size,
                "writable": await is_file_writable(apath),
                "type": type,
            }
        )

    async def write_content(self, content: Union[SaveContent, Dict]) -> None:
        if not isinstance(content, SaveContent):
            content = SaveContent(**content)
        await self._root_dir_task
        path = self.root_dir / content.path
        if content.format == "base64":
            content.content = cast(str, content.content)
            content_bytes = content.content.encode("ascii")
            await path.write_bytes(content_bytes)
        else:
            if content.format == "json":
                dict_content = cast(Dict, content.content)
                if content.type == "notebook":
                    # see https://github.com/jupyterlab/jupyterlab/issues/11005
                    if (
                        "metadata" in dict_content
                        and "orig_nbformat" in dict_content["metadata"]
                    ):
                        del dict_content["metadata"]["orig_nbformat"]
                await path.write_text(json.dumps(dict_content, indent=2))
            else:
                content.content = cast(str, content.content)
                await path.write_text(content.content)

    @property
    def file_id_manager(self):
        return FileIdManager(db_path=str(self.db_path), root_dir=str(self.root_dir))


async def get_available_path(path: anyio.Path, sep: str = "") -> anyio.Path:
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
        if not await available_path.exists():
            return available_path


async def get_file_modification_time(path: anyio.Path):
    if await path.exists():
        return datetime.utcfromtimestamp((await path.stat()).st_mtime).isoformat() + "Z"


async def get_file_creation_time(path: anyio.Path):
    if await path.exists():
        return datetime.utcfromtimestamp((await path.stat()).st_ctime).isoformat() + "Z"


async def get_file_size(path: anyio.Path) -> Optional[int]:
    if await path.exists():
        return (await path.stat()).st_size
    raise HTTPException(status_code=404, detail="Item not found")


async def is_file_writable(path: anyio.Path) -> bool:
    if await path.exists():
        if await path.is_dir():
            # FIXME
            return True
        else:
            return os.access(path, os.W_OK)
    return False
