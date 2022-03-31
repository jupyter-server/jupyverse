from typing import Optional

from fastapi_users import models  # type: ignore
from pydantic import BaseModel


class JupyterUser(BaseModel):
    anonymous: bool = True
    username: str = ""
    name: Optional[str] = None
    color: Optional[str] = None
    avatar: Optional[str] = None
    workspace: str = "{}"
    settings: str = "{}"


class User(models.BaseUser, models.BaseOAuthAccountMixin, JupyterUser):
    pass


class UserCreate(models.BaseUserCreate):
    anonymous: bool = True
    username: Optional[str] = None
    name: Optional[str] = None
    color: Optional[str] = None


class UserUpdate(models.BaseUserUpdate, JupyterUser):
    pass


class UserDB(User, models.BaseUserDB):
    pass
