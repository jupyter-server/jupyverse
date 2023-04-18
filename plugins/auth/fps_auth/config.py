from typing import Optional
from uuid import uuid4

from jupyverse_api.auth import AuthConfig


class _AuthConfig(AuthConfig):
    client_id: str = ""
    client_secret: str = ""
    redirect_uri: str = ""
    # mode: Literal["noauth", "token", "user"] = "token"
    mode: str = "token"
    token: str = uuid4().hex
    global_email: str = "guest@jupyter.com"
    cookie_secure: bool = False  # FIXME: should default to True, and set to False for tests
    clear_users: bool = False
    test: bool = False
    login_url: Optional[str] = None
    directory: Optional[str] = None
