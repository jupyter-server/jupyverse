import uuid
from typing import Dict, List

from fastapi_users import schemas
from jupyverse_api.auth import User


class JupyterUser(User):
    anonymous: bool = True
    permissions: Dict[str, List[str]]


class UserRead(schemas.BaseUser[uuid.UUID], JupyterUser):
    pass


class UserCreate(schemas.BaseUserCreate, JupyterUser):
    pass


class UserUpdate(schemas.BaseUserUpdate, JupyterUser):
    pass
