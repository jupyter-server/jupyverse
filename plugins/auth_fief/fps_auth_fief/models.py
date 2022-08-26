from typing import Dict, List, Optional

from pydantic import BaseModel


class Permissions(BaseModel):
    permissions: Dict[str, List[str]]


class UserRead(BaseModel):
    username: str = ""
    name: str = ""
    display_name: str = ""
    initials: Optional[str] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    workspace: str = "{}"
    settings: str = "{}"
