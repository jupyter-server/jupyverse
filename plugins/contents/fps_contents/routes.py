import json
import os
import shutil
from datetime import datetime
from http import HTTPStatus
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

from anyio import open_file
from fastapi import APIRouter, Depends, HTTPException, Response
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.contents import Contents, Content, SaveContent
from starlette.requests import Request

from .fileid import FileIdManager
from .models import Checkpoint, CreateContent, RenameContent


class _Contents(Contents):
    def __init__(self, app: App, auth: Auth):
        super().__init__(app=app)

        router = APIRouter()

        @router.post(
            "/api/contents/{path:path}/checkpoints",
            status_code=201,
        )
        async def create_checkpoint(
            path, user: User = Depends(auth.current_user(permissions={"contents": ["write"]}))
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
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
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

            return await self.read_content(available_path, False)

        @router.get("/api/contents")
        async def get_root_content(
            content: int,
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ):
            return await self.read_content("", bool(content))

        @router.get("/api/contents/{path:path}/checkpoints")
        async def get_checkpoint(
            path, user: User = Depends(auth.current_user(permissions={"contents": ["read"]}))
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
            user: User = Depends(auth.current_user(permissions={"contents": ["read"]})),
        ):
            return await self.read_content(path, bool(content))

        @router.put("/api/contents/{path:path}")
        async def save_content(
            path,
            request: Request,
            response: Response,
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
        ):
            content = SaveContent(**(await request.json()))
            try:
                await self.write_content(content)
            except Exception:
                raise HTTPException(status_code=404, detail=f"Error saving {content.path}")
            return await self.read_content(content.path, False)

        @router.delete(
            "/api/contents/{path:path}",
            status_code=204,
        )
        async def delete_content(
            path,
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
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
            user: User = Depends(auth.current_user(permissions={"contents": ["write"]})),
        ):
            rename_content = RenameContent(**(await request.json()))
            Path(path).rename(rename_content.path)
            return await self.read_content(rename_content.path, False)

        self.include_router(router)

    async def read_content(
        self, path: Union[str, Path], get_content: bool, as_json: bool = False
    ) -> Content:
        if isinstance(path, str):
            path = Path(path)
        content: Optional[Union[str, Dict, List[Dict]]] = None
        if get_content:
            if path.is_dir():
                content = [
                    (await self.read_content(subpath, get_content=False)).dict()
                    for subpath in path.iterdir()
                    if not subpath.name.startswith(".")
                ]
            elif path.is_file() or path.is_symlink():
                try:
                    async with await open_file(path) as f:
                        content = await f.read()
                    if as_json:
                        content = json.loads(content)
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
                    if as_json:
                        content = cast(Dict, content)
                        nb = content
                    else:
                        content = cast(str, content)
                        nb = json.loads(content)
                    for cell in nb["cells"]:
                        if "metadata" not in cell:
                            cell["metadata"] = {}
                        cell["metadata"].update({"trusted": False})
                    if not as_json:
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
        async with await open_file(content.path, "w") as f:
            if content.format == "json":
                dict_content = cast(Dict, content.content)
                if content.type == "notebook":
                    # see https://github.com/jupyterlab/jupyterlab/issues/11005
                    if "metadata" in dict_content and "orig_nbformat" in dict_content["metadata"]:
                        del dict_content["metadata"]["orig_nbformat"]
                await f.write(json.dumps(dict_content, indent=2))
            else:
                content.content = cast(str, content.content)
                await f.write(content.content)

    @property
    def file_id_manager(self):
        return FileIdManager()


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
