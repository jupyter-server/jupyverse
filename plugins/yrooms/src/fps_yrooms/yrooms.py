from datetime import datetime

import structlog
from anyio import (
    CancelScope,
    sleep,
)
from anyio.abc import TaskStatus
from jupyter_ydoc import ydocs as YDOCS
from jupyverse_api.contents import Contents
from jupyverse_api.file_id import FileId
from jupyverse_api.yrooms import AsyncChannel
from jupyverse_api.yrooms import YRoom as _YRoom
from jupyverse_api.ystore import YDocNotFound, YStoreFactory
from pycrdt import (
    Doc,
    YMessageType,
    YSyncMessageType,
    handle_sync_message,
)

from .config import YRoomsConfig

logger = structlog.get_logger()
YFILE = YDOCS["file"]


class YRoom(_YRoom):
    def __init__(
        self,
        contents: Contents,
        file_id: FileId,
        ystore_factory: YStoreFactory,
        config: YRoomsConfig,
        id: str,
        sync: bool = True,
        doc: Doc | None = None,
        permissions: dict[str, list[str]] | None = None,
    ) -> None:
        super().__init__(id, sync, doc=doc)
        self._contents = contents
        self._file_id = file_id
        self._ystore_factory = ystore_factory
        self._config = config
        self._close_room_cancel_scope: CancelScope | None = None
        self._write_to_file_cancel_scope: CancelScope | None = None
        self._id_of_file: str | None = None
        self._can_write = permissions is None or "write" in permissions.get("yjs", [])

    async def serve(self, client: AsyncChannel) -> None:
        # cancel the closing of the room if it was scheduled:
        if self._close_room_cancel_scope is not None:
            self._close_room_cancel_scope.cancel()
            self._close_room_cancel_scope = None
        kwargs = {"id": self.id}
        if self._id_of_file is not None:
            file_path = await self._get_file_path(self._id_of_file)
            assert file_path is not None
            kwargs["file_path"] = file_path
        logger.info("Client connected", **kwargs)
        await super().serve(client)
        logger.info("Client disconnected", **kwargs)

    async def run(self, *, task_status: TaskStatus[None]) -> None:
        kwargs = {"id": self.id}
        if self.id.count(":") >= 2:
            # it is a stored document (e.g. a notebook)
            self._file_format, self._file_type, self._id_of_file = self.id.split(":", 2)
            self._jupyter_ydoc = YDOCS.get(self._file_type, YFILE)(self.doc)
            self._jupyter_ydoc.ystate["file_id"] = self._id_of_file
            file_path = await self._get_file_path(self._id_of_file)
            assert file_path is not None
            kwargs["file_path"] = file_path
            logger.info("Opening collaboration room", **kwargs)
            model = await self._contents.read_content(file_path, True, self._file_format)
            assert model.last_modified is not None
            self._last_modified = to_datetime(model.last_modified)
            updates_file_path = f".{self._file_type}:{self._id_of_file}.y"
            async with self._ystore_factory(path=updates_file_path) as self._ystore:
                # try to apply Y updates from the YStore for this document
                try:
                    await self._ystore.apply_updates(self.doc)
                    read_from_source = False
                except YDocNotFound:
                    # YDoc not found in the YStore, create the document from
                    # the source file (no change history)
                    read_from_source = True
                    logger.info("Document not found in YStore", file_path=file_path, id=self.id)
                if not read_from_source:
                    # if YStore updates and source file are out-of-sync, resync updates
                    # with source
                    if await self._jupyter_ydoc.aget() != model.content:
                        read_from_source = True
                        logger.info(
                            "Document in YStore differs from file content",
                            file_path=file_path,
                            id=self.id,
                        )
                await self.task_group.start(self._write_to_ystore)
                await self.task_group.start(self._write_to_file)
                await self.task_group.start(self._watch_file)
                if read_from_source:
                    await self._jupyter_ydoc.aset(model.content)
                    await self._ystore.encode_state_as_update(self.doc)
                    logger.info("Document read from file", file_path=file_path, id=self.id)
                else:
                    logger.info("Document read from YStore", file_path=file_path, id=self.id)

                self._jupyter_ydoc.dirty = False
                await super().run(task_status=task_status)
        else:
            logger.info("Opening collaboration room", **kwargs)
            await super().run(task_status=task_status)

    async def _write_to_ystore(self, *, task_status: TaskStatus[None]) -> None:
        async with self.doc.events() as events:
            task_status.started()
            async for event in events:
                await self._ystore.write(event.update)

    async def _write_to_file(self, *, task_status: TaskStatus[None]) -> None:
        async with self.doc.events() as events:
            task_status.started()
            async for event in events:
                if self._write_to_file_cancel_scope is not None:
                    self._write_to_file_cancel_scope.cancel()
                    self._write_to_file_cancel_scope = None
                self.task_group.start_soon(self._write_to_file_later)

    async def _write_to_file_later(self) -> None:
        with CancelScope() as self._write_to_file_cancel_scope:
            await sleep(self._config.document_save_delay)
            assert self._id_of_file is not None
            file_path = await self._get_file_path(self._id_of_file)
            assert file_path is not None
            model = await self._contents.read_content(
                file_path, True, self._file_format, untrust=False
            )
            jupyter_ydoc_source = await self._jupyter_ydoc.aget()
            if model.content != jupyter_ydoc_source:
                # don't save if not needed
                # this also prevents the dirty flag from bouncing between windows of
                # the same document opened as different types (e.g. notebook/text editor)
                content = {
                    "content": jupyter_ydoc_source,
                    "format": self._file_format,
                    "path": file_path,
                    "type": self._file_type,
                }
                with CancelScope(shield=True):
                    logger.info("Saving document", file_path=file_path, id=self.id)
                    await self._contents.write_content(content)
                    model = await self._contents.read_content(file_path, False)
                    assert model.last_modified is not None
                    self._last_modified = to_datetime(model.last_modified)
                self._jupyter_ydoc.dirty = False

    async def _watch_file(self, *, task_status: TaskStatus[None]) -> None:
        assert self._id_of_file is not None
        file_path = await self._get_file_path(self._id_of_file)
        assert file_path is not None
        logger.info("Watching file", path=file_path)
        watcher = self._file_id.watch(file_path)
        task_status.started()
        async for changes in watcher:
            new_file_path = await self._get_file_path(self._id_of_file)
            assert new_file_path is not None
            if new_file_path is None:
                continue
            if new_file_path != file_path:
                # file was renamed
                self._file_id.unwatch(file_path, watcher)
                file_path = new_file_path
                # break
            await self._read_file(new_file_path)

    async def _read_file(self, file_path: str) -> None:
        model = await self._contents.read_content(file_path, False)
        assert model.last_modified is not None
        # do nothing if the file was saved by us
        if self._last_modified < to_datetime(model.last_modified):
            # the file was not saved by us, update the shared document
            model = await self._contents.read_content(file_path, True, self._file_format)
            assert model.last_modified is not None
            await self._jupyter_ydoc.aset(model.content)
            self._jupyter_ydoc.dirty = False
            logger.info("Document read from file", file_path=file_path, id=self.id)
            await self._ystore.encode_state_as_update(self._doc)
            self._last_modified = to_datetime(model.last_modified)

    async def _get_file_path(self, id_of_file: str) -> str | None:
        file_path = await self._file_id.get_path(id_of_file)
        if file_path is None:
            return None
        if file_path != self._jupyter_ydoc.path:
            self._jupyter_ydoc.path = file_path
        return file_path

    async def handle_message(self, message: bytes, client: AsyncChannel) -> None:
        match message[0]:
            case YMessageType.SYNC:
                _message = message[1:]
                if self._can_write or _message[0] not in {
                    YSyncMessageType.SYNC_UPDATE,
                    YSyncMessageType.SYNC_STEP2,
                }:
                    reply = handle_sync_message(_message, self._doc)
                    if reply is not None:
                        await client.send(reply)
            case YMessageType.AWARENESS:
                for client in self.clients:
                    await client.send(message)

    async def close(self) -> None:
        with CancelScope() as self._close_room_cancel_scope:
            kwargs = {"id": self.id}
            if self._id_of_file is not None:
                file_path = await self._get_file_path(self._id_of_file)
                assert file_path is not None
                kwargs["file_path"] = file_path
                await sleep(self._config.document_cleanup_delay)
            await super().close()
            logger.info("Closed collaboration room", **kwargs)


def to_datetime(iso_date: str) -> datetime:
    return datetime.fromisoformat(iso_date.rstrip("Z"))
