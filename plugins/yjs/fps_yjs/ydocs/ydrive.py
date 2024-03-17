from __future__ import annotations

from contextlib import AsyncExitStack
from functools import partial
from pathlib import Path
from typing import Any, Callable, Dict, List, cast

from anyio import create_task_group
from anyio.abc import TaskGroup
from pycrdt import Doc, Map, MapEvent

from jupyverse_api.auth import User
from jupyverse_api.contents import Content, Contents

from .ybasedoc import YBaseDoc


class YDrive(YBaseDoc):
    _starting: bool
    _task_group: TaskGroup | None

    def __init__(
            self,
            contents: Contents,
            ydoc: Doc | None = None,
            root_dir: Path | str | None = None,
        ):
        super().__init__(ydoc)
        self._root_dir = Path() if root_dir is None else Path(root_dir)
        self._ydoc["content"] = self._ycontent = self._new_dir_content()
        self._ycontent.observe_deep(self._callback)
        self._user = User()
        self._starting = False
        self._task_group = None
        self._contents = contents
        self._watcher = contents.file_id_manager.watch(".")

    async def __aenter__(self) -> YDrive:
        if self._task_group is not None:
            raise RuntimeError("YDrive already running")

        async with AsyncExitStack() as exit_stack:
            tg = create_task_group()
            self._task_group = await exit_stack.enter_async_context(tg)
            self._exit_stack = exit_stack.pop_all()

        assert self._task_group is not None
        self._task_group.start_soon(self._process_file_changes)

        return self

    async def _process_file_changes(self):
        async for change in self._watcher:
            change_, path = change
            # no exception should stop watching the file system
            try:
                if change_ == self._contents.file_id_manager.Change.deleted:
                    current_parent_content = await self._get(path.parent)
                    if path.name in current_parent_content["content"]:
                        del current_parent_content["content"][path.name]
                elif change_ in (
                    self._contents.file_id_manager.Change.added,
                    self._contents.file_id_manager.Change.modified,
                ):
                    real_parent_content = await self._get_directory_content(path.parent)
                    # file change might be out of sync with current directory list
                    if path.name in real_parent_content.prelim:
                        current_parent_content = await self._get(path.parent)
                        current_parent_content["content"][path.name] = \
                            real_parent_content.prelim[path.name]
            except Exception:
                pass

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        if self._task_group is None:
            raise RuntimeError("YDrive not running")

        self._task_group.cancel_scope.cancel()
        self._task_group = None
        return await self._exit_stack.__aexit__(exc_type, exc_value, exc_tb)

    def _callback(self, events):
        for event in events:
            if isinstance(event, MapEvent):
                current = self._ycontent
                for p in event.path:
                    current = current[p]
                for key, val in event.keys.items():
                    action = val.get("action")
                    if action == "delete":
                        path = "/".join(event.path[1::2] + [key])
                        self._task_group.start_soon(self._try_delete_content, path)
                    elif action == "add":
                        path = "/".join(event.path[1::2] + [key])
                        new_content = val["newValue"]
                        if "copy" in new_content:
                            self._task_group.start_soon(self._try_copy, new_content, path)
                        elif "move" in new_content:
                            self._task_group.start_soon(self._try_move, new_content, path)
                        elif new_content["is_dir"]:
                            self._task_group.start_soon(self._try_create_directory, path)
                        else:
                            self._task_group.start_soon(self._try_create_file, path)
                    elif action == "update":
                        if key == "populate" and not val["oldValue"] and val["newValue"]:
                            path = "/".join(event.path[1::2])
                            self._task_group.start_soon(self.ls, path)

    @property
    def version(self) -> str:
        return "1.0.0"

    def _new_dir_content(self) -> Map:
        return Map({"is_dir": True, "populate": False, "content": None})

    def _new_file_content(self, content: Content | None = None) -> Map:
        if content is None:
            return Map(
                {
                    "is_dir": False,
                    "size": 0,
                    "last_modified": None,
                    "created": None,
                    "writable": True,
                }
            )
        return Map(
            {
                "is_dir": False,
                "size": content.size,
                "last_modified": content.last_modified,
                "created": content.created,
                "writable": content.writable,
            }
        )

    def _copy_or_move_content(self, action: str, content: Map, from_path: Path) -> Map:
        if content["is_dir"]:
            new_content = self._new_dir_content()
        else:
            new_content = self._new_file_content()
        new_content.prelim[action] = str(from_path)
        return new_content

    async def _get_directory_content(self, path: Path) -> Map:
        res = {}
        content = await self._contents.read_content(self._root_dir / path, get_content=True)
        if content.type == "directory":
            directory_content = cast(List[Dict], content.content)
            for entry in directory_content:
                _content = Content(**entry)
                if _content.type == "directory":
                    res[_content.name] = self._new_dir_content()
                else:
                    res[_content.name] = self._new_file_content(_content)
        return Map(res)

    async def _maybe_populate_dir(self, path: Path, content: Map):
        if content["content"] is None:
            with content.doc.transaction():
                content["content"] = await self._get_directory_content(path)
                if not content["populate"]:
                    content["populate"] = True

    async def _get(self, path: Path | str | None = None) -> Map:
        path = Path() if path is None else Path(path)
        current_content = self._ycontent
        await self._maybe_populate_dir(path, self._ycontent)
        cwd = Path()
        last_idx = len(path.parts) - 1
        for idx, part in enumerate(path.parts):
            try:
                current_content = current_content["content"][part]
            except KeyError:
                raise FileNotFoundError(f'No entry "{part}" in "{cwd}".')
            if current_content["is_dir"]:
                cwd /= part
                await self._maybe_populate_dir(cwd, current_content)
            elif idx < last_idx:
                raise RuntimeError(f'Entry "{part}" in "{cwd}" is not a directory.')
        return current_content

    async def get(self, path: Path | str | None = None) -> dict:
        return dict(await self._get(path))

    async def ls(self, path: Path | str | None = None) -> dict:
        path = Path() if path is None else Path(path)
        entry = await self.get(path)
        if entry["is_dir"]:
            res = {}
            content = entry["content"]
            for k1, v1 in content.items():
                if v1["is_dir"]:
                    res[k1] = {k2: v2 for k2, v2 in v1.items() if k2 != "content"}
                else:
                    res[k1] = dict(v1)
        else:
            res = dict(entry)
        return res

    async def _try_copy(self, new_content: Map, to_path: str):
        try:
            await self._contents.copy_content(new_content["copy"], to_path)
            del new_content["copy"]
        except Exception:
            # the operation didn't succeed, maybe revert the shared model change
            await self._update(to_path)

    async def _try_move(self, new_content: Map, to_path: str):
        try:
            from_path = Path(new_content["move"])
            await self._contents.move_content(str(from_path), to_path)
            parent_content = await self._get(from_path.parent)
            del parent_content["content"][from_path.name]
            del new_content["move"]
        except Exception:
            # the operation didn't succeed, maybe revert the shared model change
            await self._update(to_path)

    async def _try_delete_content(self, path: str) -> None:
        try:
            await self._contents.delete_content(path, self._user)
        except Exception:
            # the operation didn't succeed, maybe revert the shared model change
            await self._update(path)

    async def _try_create_directory(self, path: str) -> None:
        try:
            await self._contents.create_directory(path)
        except Exception:
            # the operation didn't succeed, maybe revert the shared model change
            await self._update(path)

    async def _try_create_file(self, path: str) -> None:
        try:
            await self._contents.create_file(path)
        except Exception:
            # the operation didn't succeed, maybe revert the shared model change
            await self._update(path)

    async def _update(self, path: Path | str) -> None:
        path = Path(path) if isinstance(path, str) else path
        real_parent_content = await self._get_directory_content(path.parent)
        current_parent_content = await self._get(path.parent)
        if path.name in real_parent_content.prelim:
            if path.name not in current_parent_content:
                current_parent_content[path.name] = real_parent_content.prelim[path.name]
        else:
            if path.name in current_parent_content:
                del current_parent_content[path.name]

    async def delete(self, path: Path | str) -> None:
        path = Path(path) if isinstance(path, str) else path
        if not path.parts:
            raise RuntimeError("Cannot delete root directory")
        parent_content = await self._get(path.parent)
        del parent_content["content"][path.name]

    async def create_directory(self, path: Path | str):
        return await self.create(path, is_dir=True)

    async def create_file(self, path: Path | str):
        return await self.create(path, is_dir=False)

    async def create(self, path: Path | str, is_dir: bool):
        path = Path(path) if isinstance(path, str) else path
        if not path.parts:
            raise RuntimeError("Cannot create root directory")
        parent_content = await self._get(path.parent)
        if is_dir:
            parent_content["content"][path.name] = self._new_dir_content()
        else:
            parent_content["content"][path.name] = self._new_file_content()

    async def move(self, from_path: Path | str, to_path: Path | str):
        await self._copy_or_move("move", from_path, to_path)

    async def copy(self, from_path: Path | str, to_path: Path | str):
        await self._copy_or_move("copy", from_path, to_path)

    async def _copy_or_move(self, action: str, from_path: Path | str, to_path: Path | str):
        from_path = Path(from_path) if isinstance(from_path, str) else from_path
        to_path = Path(to_path) if isinstance(to_path, str) else to_path
        if not from_path.parts:
            raise RuntimeError(f"Cannot {action} root directory")
        if not to_path.parts:
            raise RuntimeError(f"Cannot {action} to root directory")
        from_parent_content = await self._get(from_path.parent)
        to_parent_content = await self._get(to_path.parent)
        to_parent_content["content"][to_path.name] = self._copy_or_move_content(
            action, from_parent_content["content"][from_path.name], from_path
        )

    def set(self, value) -> None:
        raise RuntimeError("Cannot set a YDrive")

    def observe(self, callback: Callable[[str, Any], None]) -> None:
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(partial(callback, "state"))
        self._subscriptions[self._ycontent] = self._ycontent.observe_deep(
            partial(callback, "content")
        )
