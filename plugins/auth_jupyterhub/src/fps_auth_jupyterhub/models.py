from jupyverse_api.auth import User
from pydantic import ConfigDict


class JupyterHubUser(User):
    model_config = ConfigDict(from_attributes=True)

    token: str
    anonymous: bool = True
    permissions: dict[str, list[str]]
