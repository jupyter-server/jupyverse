import json
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

from fps.config import Config  # type: ignore
from fps.hooks import register_router  # type: ignore
from fastapi import APIRouter, Depends
from starlette.requests import Request  # type: ignore

from fps_auth.routes import users  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_auth.config import AuthConfig  # type: ignore

from .models import Checkpoint, Content, SaveContent

router = APIRouter()
auth_config = Config(AuthConfig)


@router.post(
    "/api/contents",
    status_code=201,
)
async def create_content(
    request: Request,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    create_content = await request.json()
    path = Path(create_content["path"])
    if create_content["type"] == "notebook":
        available_path = get_available_path(path / "Untitled.ipynb")
        with open(available_path, "w") as f:
            json.dump(
                {"cells": [], "metadata": {}, "nbformat": 4, "nbformat_minor": 5}, f
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
    else:
        available_path = get_available_path(path / ("untitled" + create_content["ext"]))
        open(available_path, "w").close()

    return Content(**get_path_content(available_path, False))


@router.get("/api/contents")
async def get_root_content(
    content: int,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    return Content(**get_path_content(Path(""), bool(content)))


@router.get("/api/contents/{path:path}/checkpoints")
async def get_checkpoint(
    path, user: User = Depends(users.current_user(optional=auth_config.disable_auth))
):
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
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    return Content(**get_path_content(Path(path), bool(content)))


@router.put("/api/contents/{path:path}")
async def save_content(
    request: Request,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    save_content = SaveContent(**(await request.json()))
    try:
        with open(save_content.path, "w") as f:
            if save_content.format == "json":
                dict_content = cast(Dict, save_content.content)
                if save_content.type == "notebook":
                    # see https://github.com/jupyterlab/jupyterlab/issues/11005
                    if (
                        "metadata" in dict_content
                        and "orig_nbformat" in dict_content["metadata"]
                    ):
                        del dict_content["metadata"]["orig_nbformat"]
                    json.dump(dict_content, f, indent=2)
            else:
                str_content = cast(str, save_content.content)
                f.write(str_content)
    except Exception:
        # FIXME: return error code?
        pass
    return Content(**get_path_content(Path(save_content.path), False))


@router.post(
    "/api/contents/{path:path}/checkpoints",
    status_code=201,
)
async def create_checkpoint(
    path, user: User = Depends(users.current_user(optional=auth_config.disable_auth))
):
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


def get_path_content(path: Path, get_content: bool):
    content: Optional[Union[str, List[Dict]]] = None
    if get_content:
        if path.is_dir():
            content = [
                get_path_content(subpath, get_content=False)
                for subpath in path.iterdir()
                if not subpath.name.startswith(".")
            ]
        elif path.is_file():
            try:
                with open(path) as f:
                    content = f.read()
            except Exception:
                # FIXME: return error code?
                pass
    format: Optional[str] = None
    if path.is_dir():
        size = None
        type = "directory"
        format = "json"
        mimetype = None
    else:
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


def get_available_path(path: Path):
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
        available_path = directory / (name.stem + i_str + name.suffix)
        if not available_path.exists():
            return available_path


r = register_router(router)
