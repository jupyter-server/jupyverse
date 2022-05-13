import uuid
from typing import Optional

from fastapi_users import schemas
from pydantic import BaseModel


class JupyterUser(BaseModel):
    anonymous: bool = True
    username: str = ""
    name: Optional[str] = None
    color: Optional[str] = None
    avatar: Optional[str] = None
    workspace: str = "{}"
    settings: str = "{}"


class UserRead(schemas.BaseUser[uuid.UUID], JupyterUser):
    pass


class UserCreate(schemas.BaseUserCreate):
    anonymous: bool = True
    username: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate, JupyterUser):
    pass
