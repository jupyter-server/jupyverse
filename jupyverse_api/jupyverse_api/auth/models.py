from typing import Optional
from pydantic import BaseModel


class User(BaseModel):
    username: str = ""
    name: str = ""
    display_name: str = ""
    initials: Optional[str] = None
    color: Optional[str] = None
    avatar_url: Optional[str] = None
    workspace: str = "{}"
    settings: str = "{}"
