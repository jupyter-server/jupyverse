from pydantic import BaseModel


class CreateRoomId(BaseModel):
    format: str
    type: str
