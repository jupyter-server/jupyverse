from pydantic import BaseModel


class Backend(BaseModel):
    backend: str


class Install(BaseModel):
    installed: bool
