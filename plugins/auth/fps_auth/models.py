from typing import Optional

from pydantic import BaseModel
from fastapi_users import models  # type: ignore


class JupyterUser(BaseModel):
    initialized: bool = False
    anonymous: bool = True
    name: Optional[str] = None
    username: Optional[str] = None
    color: Optional[str] = None
    avatar: Optional[str] = None
    logged_in: bool = False
    workspace: str = "{}"
    settings: str = "{}"


class User(models.BaseUser, models.BaseOAuthAccountMixin, JupyterUser):
    pass


class UserCreate(models.BaseUserCreate):
    name: Optional[str] = None
    username: Optional[str] = None
    color: Optional[str] = None


class UserUpdate(models.BaseUserUpdate, JupyterUser):
    pass


class UserDB(User, models.BaseUserDB):
    pass
