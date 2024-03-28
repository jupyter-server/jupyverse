from pydantic import BaseModel


class CreateDocumentSession(BaseModel):
    format: str
    type: str


class MergeRoom(BaseModel):
    fork_roomid: str
    root_roomid: str
