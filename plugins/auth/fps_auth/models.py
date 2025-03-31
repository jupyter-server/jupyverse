import uuid

from fastapi_users import schemas

from jupyverse_api.auth import User


class JupyterUser(User):
    anonymous: bool = True
    permissions: dict[str, list[str]]


class UserRead(schemas.BaseUser[uuid.UUID], JupyterUser):
    pass


class UserCreate(schemas.BaseUserCreate, JupyterUser):
    pass


class UserUpdate(schemas.BaseUserUpdate, JupyterUser):
    pass
