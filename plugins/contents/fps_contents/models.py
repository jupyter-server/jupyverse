from typing import Optional

from pydantic import BaseModel


class Checkpoint(BaseModel):
    id: str
    last_modified: str


class CreateContent(BaseModel):
    ext: Optional[str]
    path: str
    type: str


class RenameContent(BaseModel):
    path: str
