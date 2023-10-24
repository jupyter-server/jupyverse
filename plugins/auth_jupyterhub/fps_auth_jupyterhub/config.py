from pydantic import Field

from jupyverse_api.auth import AuthConfig


class AuthJupyterHubConfig(AuthConfig):
    db_url: str = Field(
        description="The connection URL passed to create_engine()",
        default="sqlite+aiosqlite:///:memory:",
    )
