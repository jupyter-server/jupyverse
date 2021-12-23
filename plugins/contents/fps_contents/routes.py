from http import HTTPStatus
import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

from fps.hooks import register_router  # type: ignore
from fastapi import APIRouter, Depends, HTTPException, Response
from starlette.requests import Request  # type: ignore
from anyio import open_file

from fps_auth.backends import current_user  # type: ignore
from fps_auth.models import User  # type: ignore

from .models import Checkpoint, Content, SaveContent, CreateContent, RenameContent

router = APIRouter()


@router.post(
    "/api/contents/{path:path}/checkpoints",
    status_code=201,
)
async def create_checkpoint(path, user: User = Depends(current_user)):
    src_path = Path(path)
    dst_path = (
        Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
    )
    try:
        dst_path.parent.mkdir(exist_ok=True)
        shutil.copyfile(src_path, dst_path)
    except Exception:
        # FIXME: return error code?
        return []
    mtime = get_file_modification_time(dst_path)
    return Checkpoint(**{"id": "checkpoint", "last_modified": mtime})


@router.post(
    "/api/contents{path:path}",
    status_code=201,
)
async def create_content(
    path: Optional[str],
    request: Request,
    user: User = Depends(current_user),
):
    create_content = CreateContent(**(await request.json()))
    content_path = Path(create_content.path)
    if create_content.type == "notebook":
        available_path = get_available_path(content_path / "Untitled.ipynb")
        async with await open_file(available_path, "w") as f:
            await f.write(
                json.dumps(
                    {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}
                )
            )
        src_path = available_path
        dst_path = (
            Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
        )
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
        available_path = get_available_path(
            content_path / ("untitled" + create_content.ext)
        )
        open(available_path, "w").close()

    return Content(**await get_path_content(available_path, False))


@router.get("/api/contents")
async def get_root_content(
    content: int,
    user: User = Depends(current_user),
):
    return Content(**await get_path_content(Path(""), bool(content)))


@router.get("/api/contents/{path:path}/checkpoints")
async def get_checkpoint(path, user: User = Depends(current_user)):
    src_path = Path(path)
    dst_path = (
        Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
    )
    if not dst_path.exists():
        return []
    mtime = get_file_modification_time(dst_path)
    return [Checkpoint(**{"id": "checkpoint", "last_modified": mtime})]


@router.get("/api/contents/{path:path}")
async def get_content(
    path: str,
    content: int,
    user: User = Depends(current_user),
):
    return Content(**await get_path_content(Path(path), bool(content)))


@router.put("/api/contents/{path:path}")
async def save_content(
    request: Request,
    user: User = Depends(current_user),
):
    save_content = SaveContent(**(await request.json()))
    try:
        async with await open_file(save_content.path, "w") as f:
            if save_content.format == "json":
                dict_content = cast(Dict, save_content.content)
                if save_content.type == "notebook":
                    # see https://github.com/jupyterlab/jupyterlab/issues/11005
                    if (
                        "metadata" in dict_content
                        and "orig_nbformat" in dict_content["metadata"]
                    ):
                        del dict_content["metadata"]["orig_nbformat"]
                    await f.write(json.dumps(dict_content, indent=2))
            else:
                str_content = cast(str, save_content.content)
                await f.write(str_content)
    except Exception:
        # FIXME: return error code?
        pass
    return Content(**await get_path_content(Path(save_content.path), False))


@router.delete(
    "/api/contents/{path:path}",
    status_code=204,
)
async def delete_content(
    path,
    user: User = Depends(current_user),
):
    p = Path(path)
    if p.exists():
        if p.is_dir():
            shutil.rmtree(p)
        else:
            p.unlink()
    return Response(status_code=HTTPStatus.NO_CONTENT.value)


@router.patch("/api/contents/{path:path}")
async def rename_content(
    path,
    request: Request,
    user: User = Depends(current_user),
):
    rename_content = RenameContent(**(await request.json()))
    Path(path).rename(rename_content.path)
    return Content(**await get_path_content(Path(rename_content.path), False))


def get_file_modification_time(path: Path):
    if path.exists():
        return datetime.utcfromtimestamp(path.stat().st_mtime).isoformat() + "Z"


def get_file_creation_time(path: Path):
    if path.exists():
        return datetime.utcfromtimestamp(path.stat().st_ctime).isoformat() + "Z"


def get_file_size(path: Path) -> Optional[int]:
    if path.exists():
        return path.stat().st_size
    return None


def is_file_writable(path: Path) -> bool:
    if path.exists():
        if path.is_dir():
            # FIXME
            return True
        else:
            return os.access(path, os.W_OK)
    return False


async def get_path_content(path: Path, get_content: bool):
    content: Optional[Union[str, List[Dict]]] = None
    if get_content:
        if path.is_dir():
            content = [
                await get_path_content(subpath, get_content=False)
                for subpath in path.iterdir()
                if not subpath.name.startswith(".")
            ]
        elif path.is_file():
            try:
                async with await open_file(path) as f:
                    content = await f.read()
            except Exception:
                raise HTTPException(status_code=404, detail="Item not found")
    format: Optional[str] = None
    if path.is_dir():
        size = None
        type = "directory"
        format = "json"
        mimetype = None
    elif path.is_file():
        size = get_file_size(path)
        if path.suffix == ".ipynb":
            type = "notebook"
            format = None
            mimetype = None
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

    return {
        "name": path.name,
        "path": str(path),
        "last_modified": get_file_modification_time(path),
        "created": get_file_creation_time(path),
        "content": content,
        "format": format,
        "mimetype": mimetype,
        "size": size,
        "writable": is_file_writable(path),
        "type": type,
    }


def get_available_path(path: Path, sep: str = ""):
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


r = register_router(router)
