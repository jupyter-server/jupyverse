from pydantic import BaseModel


class Terminal(BaseModel):
    name: str
    last_activity: str
