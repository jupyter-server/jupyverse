from pydantic import BaseModel


class UserRead(BaseModel):
    workspace: str = "{}"
    settings: str = "{}"
