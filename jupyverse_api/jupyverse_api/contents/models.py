from __future__ import annotations

from pydantic import BaseModel


class Checkpoint(BaseModel):
    id: str
    last_modified: str


class Content(BaseModel):
    name: str
    path: str
    last_modified: str | None = None
    created: str | None = None
    content: list[dict] | str | dict | None = None
    format: str | None = None
    mimetype: str | None = None
    size: int | None = None
    writable: bool
    type: str


class CreateContent(BaseModel):
    ext: str | None = None
    path: str
    type: str


class SaveContent(BaseModel):
    content: str | dict | None = None
    format: str
    path: str
    type: str


class RenameContent(BaseModel):
    path: str
