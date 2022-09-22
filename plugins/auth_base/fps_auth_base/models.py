from typing import Dict, List

from pydantic import BaseModel


class Permissions(BaseModel):
    permissions: Dict[str, List[str]]


class BaseUser(Permissions):
    username: str = ""
