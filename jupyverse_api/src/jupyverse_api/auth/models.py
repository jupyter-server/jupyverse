from __future__ import annotations

from pydantic import BaseModel


class User(BaseModel):
    username: str = ""
    name: str = ""
    display_name: str = ""
    initials: str | None = None
    color: str | None = None
    avatar_url: str | None = None
    workspace: str = "{}"
    settings: str = "{}"
