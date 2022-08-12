import uuid
from typing import Dict, List, Optional

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
    permissions: str = "{}"


class Permissions(BaseModel):
    __root__: Dict[str, List[str]]

    def items(self):
        return self.__root__.items()


class UserRead(schemas.BaseUser[uuid.UUID], JupyterUser):
    pass


class UserCreate(schemas.BaseUserCreate):
    anonymous: bool = True
    username: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None


class UserUpdate(schemas.BaseUserUpdate, JupyterUser):
    pass
