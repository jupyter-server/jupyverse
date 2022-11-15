import json
import shutil
from http import HTTPStatus
from pathlib import Path
from typing import Optional

from anyio import open_file
from fastapi import APIRouter, Depends, HTTPException, Response
from fps.hooks import register_router  # type: ignore
from fps_auth_base import User, current_user  # type: ignore
from starlette.requests import Request  # type: ignore

from .models import Checkpoint, CreateContent, RenameContent, SaveContent
from .utils import (
    get_available_path,
    get_file_modification_time,
    read_content,
    write_content,
)

router = APIRouter()


@router.post(
    "/api/contents/{path:path}/checkpoints",
    status_code=201,
)
async def create_checkpoint(
    path, user: User = Depends(current_user(permissions={"contents": ["write"]}))
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


@router.post(
    "/api/contents{path:path}",
    status_code=201,
)
async def create_content(
    path: Optional[str],
    request: Request,
    user: User = Depends(current_user(permissions={"contents": ["write"]})),
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

    return await read_content(available_path, False)


@router.get("/api/contents")
async def get_root_content(
    content: int,
    user: User = Depends(current_user(permissions={"contents": ["read"]})),
):
    return await read_content("", bool(content))


@router.get("/api/contents/{path:path}/checkpoints")
async def get_checkpoint(
    path, user: User = Depends(current_user(permissions={"contents": ["read"]}))
):
    src_path = Path(path)
    dst_path = Path(".ipynb_checkpoints") / f"{src_path.stem}-checkpoint{src_path.suffix}"
    if not dst_path.exists():
        return []
    mtime = get_file_modification_time(dst_path)
    return [Checkpoint(**{"id": "checkpoint", "last_modified": mtime})]


@router.get("/api/contents/{path:path}")
async def get_content(
    path: str,
    content: int = 0,
    user: User = Depends(current_user(permissions={"contents": ["read"]})),
):
    return await read_content(path, bool(content))


@router.put("/api/contents/{path:path}")
async def save_content(
    path,
    request: Request,
    response: Response,
    user: User = Depends(current_user(permissions={"contents": ["write"]})),
):
    content = SaveContent(**(await request.json()))
    try:
        await write_content(content)
    except Exception:
        raise HTTPException(status_code=404, detail=f"Error saving {content.path}")
    return await read_content(content.path, False)


@router.delete(
    "/api/contents/{path:path}",
    status_code=204,
)
async def delete_content(
    path,
    user: User = Depends(current_user(permissions={"contents": ["write"]})),
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
    user: User = Depends(current_user(permissions={"contents": ["write"]})),
):
    rename_content = RenameContent(**(await request.json()))
    Path(path).rename(rename_content.path)
    return await read_content(rename_content.path, False)


r = register_router(router)
