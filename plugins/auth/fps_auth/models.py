import uuid
from typing import Dict, List, Optional

from fastapi_users import schemas
from pydantic import BaseModel


class Permissions(BaseModel):
    permissions: Dict[str, List[str]]


class JupyterUser(Permissions):
    anonymous: bool = True
    username: str = ""
    name: str = ""
    display_name: str = ""
    initials: Optional[str] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    workspace: str = "{}"
    settings: str = "{}"


class UserRead(schemas.BaseUser[uuid.UUID], JupyterUser):
    pass


class UserCreate(schemas.BaseUserCreate, JupyterUser):
    pass


class UserUpdate(schemas.BaseUserUpdate, JupyterUser):
    pass
