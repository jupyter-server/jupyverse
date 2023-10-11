from typing import Dict, List, Optional, Union

from pydantic import BaseModel


class Checkpoint(BaseModel):
    id: str
    last_modified: str


class Content(BaseModel):
    name: str
    path: str
    last_modified: Optional[str] = None
    created: Optional[str] = None
    content: Optional[Union[List[Dict], str, Dict]] = None
    format: Optional[str] = None
    mimetype: Optional[str] = None
    size: Optional[int] = None
    writable: bool
    type: str


class CreateContent(BaseModel):
    ext: Optional[str] = None
    path: str
    type: str


class SaveContent(BaseModel):
    content: Optional[Union[str, Dict]] = None
    format: str
    path: str
    type: str


class RenameContent(BaseModel):
    path: str
