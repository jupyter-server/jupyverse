from jupyverse_api.auth import AuthConfig
from pydantic import Field


class AuthJupyterHubConfig(AuthConfig):
    db_url: str = Field(
        description="The connection URL passed to create_engine()",
        default="sqlite+aiosqlite:///:memory:",
    )
