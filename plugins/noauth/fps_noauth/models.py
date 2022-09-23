from pydantic import BaseModel


class BaseUser(BaseModel):
    username: str = ""
