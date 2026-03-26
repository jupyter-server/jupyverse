import base64
import json
import os
import shutil
from datetime import datetime, timezone
from http import HTTPStatus
from typing import cast

import structlog
from anyio import CancelScope, Path, to_thread
from fastapi import HTTPException, Response
from jupyverse_auth import User
from jupyverse_contents import Contents
from jupyverse_contents.models import (
    Checkpoint,
    Content,
    CreateContent,
    RenameContent,
    SaveContent,
)
from starlette.requests import Request

logger = structlog.get_logger()


class _Contents(Contents):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.root_dir: str | None = None

    async def init_root_dir(self, user: User | None = None) -> None:
        try:
            content = await self.get_root_content(content=0, user=user)
            self.root_dir = content.path
        except Exception as e:
            logger.error("Failed to initialize root_dir", error=str(e))
            raise RuntimeError(f"Could not determine root directory: {e}") from e

    async def create_checkpoint(
        self,
        path,
        user: User,
    ):
        src_path = Path(path)
        dst_path = Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
        try:
            await dst_path.parent.mkdir(exist_ok=True)
            await to_thread.run_sync(shutil.copyfile, src_path, dst_path)
        except Exception:
            # FIXME: return error code?
            return []
        mtime = await get_file_modification_time(dst_path)
        return Checkpoint(**{"id": "checkpoint", "last_modified": mtime})

    async def create_content(
        self,
        path: str | None,
        request: Request,
        user: User,
    ):
        create_content = CreateContent(**(await request.json()))
        content_path = Path(create_content.path)
        if create_content.type == "notebook":
            available_path = await get_available_path(content_path / "Untitled.ipynb")
            await available_path.write_text(
                json.dumps({"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5})
            )
            src_path = available_path
            dst_path = Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
            try:
                await dst_path.parent.mkdir(exist_ok=True)
                await to_thread.run_sync(shutil.copyfile, src_path, dst_path)
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
        if await p.exists():
            if await p.is_dir():
                await to_thread.run_sync(shutil.rmtree, p)
            else:
                await p.unlink()
        return Response(status_code=HTTPStatus.NO_CONTENT.value)

    async def rename_content(
        self,
        path,
        request: Request,
        user: User,
    ):
        rename_content = RenameContent(**(await request.json()))
        await Path(path).rename(rename_content.path)
        return await self.read_content(rename_content.path, False)

    async def read_content(
        self,
        path: str | Path,
        get_content: bool,
        file_format: str | None = None,
        untrust: bool = True,
    ) -> Content:
        path = Path(path)
        async with self.file_lock(str(path)):
            content: str | dict | list[dict] | None = None
            if get_content:
                if await path.is_dir():
                    content = [
                        (await self.read_content(subpath, get_content=False)).model_dump()
                        async for subpath in path.iterdir()
                        if not subpath.name.startswith(".")
                    ]
                elif await path.is_file() or await path.is_symlink():
                    try:
                        content_bytes = await path.read_bytes()
                        if file_format == "base64":
                            content = base64.b64encode(content_bytes).decode("ascii")
                        elif file_format == "json":
                            content = json.loads(content_bytes)
                        else:
                            content = content_bytes.decode()
                    except Exception:
                        raise HTTPException(status_code=404, detail="Item not found")
            format: str | None = None
            if await path.is_dir():
                size = None
                type = "directory"
                format = "json"
                mimetype = None
            elif await path.is_file() or await path.is_symlink():
                size = await get_file_size(path)
                if path.suffix == ".ipynb":
                    type = "notebook"
                    format = None
                    mimetype = None
                    if content is not None:
                        nb: dict
                        if file_format == "json":
                            content = cast(dict, content)
                            nb = content
                        else:
                            content = cast(str, content)
                            nb = json.loads(content)
                        for cell in nb["cells"]:
                            if untrust:
                                if "metadata" not in cell:
                                    cell["metadata"] = {}
                                cell["metadata"].update({"trusted": False})
                            if cell["cell_type"] == "code":
                                cell_source = cell["source"]
                                if not isinstance(cell_source, str):
                                    cell["source"] = "".join(cell_source)
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
                    "last_modified": await get_file_modification_time(path),
                    "created": await get_file_creation_time(path),
                    "content": content,
                    "format": format,
                    "mimetype": mimetype,
                    "size": size,
                    "writable": await is_file_writable(path),
                    "type": type,
                }
            )

    async def write_content(self, content: SaveContent | dict) -> None:
        # writing can never be cancelled, otherwise it would corrupt the file
        with CancelScope(shield=True):
            if not isinstance(content, SaveContent):
                content = SaveContent(**content)
            async with self.file_lock(content.path):
                if content.format == "base64":
                    content.content = cast(str, content.content)
                    content_bytes = content.content.encode("ascii")
                    await Path(content.path).write_bytes(content_bytes)
                else:
                    if content.format == "json":
                        dict_content = cast(dict, content.content)
                        if content.type == "notebook":
                            # see https://github.com/jupyterlab/jupyterlab/issues/11005
                            if (
                                "metadata" in dict_content
                                and "orig_nbformat" in dict_content["metadata"]
                            ):
                                del dict_content["metadata"]["orig_nbformat"]
                        try:
                            str_content = json.dumps(dict_content, indent=2)
                        except TypeError as exception:
                            logger.warning(
                                "Error saving file", path=content.path, exc_info=exception
                            )
                        else:
                            await Path(content.path).write_text(str_content)
                    else:
                        content.content = cast(str, content.content)
                        await Path(content.path).write_text(content.content)


async def get_available_path(path: Path, sep: str = "") -> Path:
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


async def get_file_modification_time(path: Path):
    if await path.exists():
        return (
            datetime.fromtimestamp((await path.stat()).st_mtime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )


async def get_file_creation_time(path: Path):
    if await path.exists():
        return (
            datetime.fromtimestamp((await path.stat()).st_ctime, tz=timezone.utc)
            .isoformat()
            .replace("+00:00", "Z")
        )


async def get_file_size(path: Path) -> int | None:
    if await path.exists():
        return (await path.stat()).st_size
    raise HTTPException(status_code=404, detail="Item not found")


async def is_file_writable(path: Path) -> bool:
    if await path.exists():
        if await path.is_dir():
            # FIXME
            return True
        else:
            return await to_thread.run_sync(os.access, path, os.W_OK)
    return False
