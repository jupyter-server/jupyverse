from enum import Enum
from uuid import uuid4
from typing import Optional

from pydantic import BaseModel
from fastapi_users import models  # type: ignore


class Role(Enum):
    ADMIN = 1
    READ = 2
    WRITE = 3
    RUN = 4

class JupyterUser(BaseModel):
    username: str = f"{uuid4()}@jupyter.com"
    email: str = f"{uuid4()}@jupyter.com"
    role: Role = Role.READ
    anonymous: bool = True
    connected: bool = False
    name: Optional[str] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    workspace: Optional[str] = "{}"
    settings: Optional[str] = "{}"

class User(models.BaseUser, models.BaseOAuthAccountMixin, JupyterUser):
    pass


class UserCreate(models.BaseUserCreate, JupyterUser):
    pass


class UserUpdate(models.BaseUserUpdate):
    role: Optional[Role] = Role.READ
    name: Optional[str] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    workspace: Optional[str] = "{}"
    settings: Optional[str] = "{}"

class UserDB(User, models.BaseUserDB):
    pass
