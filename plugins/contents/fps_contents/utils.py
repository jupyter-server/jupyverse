import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Union, cast

from anyio import open_file
from fastapi import HTTPException

from .models import Content, SaveContent


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


async def read_content(path: Union[str, Path], get_content: bool, as_json: bool = False) -> Content:
    if isinstance(path, str):
        path = Path(path)
    content: Optional[Union[str, Dict, List[Dict]]] = None
    if get_content:
        if path.is_dir():
            content = [
                (await read_content(subpath, get_content=False)).dict()
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


async def write_content(content: Union[SaveContent, Dict]) -> None:
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
