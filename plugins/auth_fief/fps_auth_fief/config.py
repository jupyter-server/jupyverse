from jupyverse_api.auth import AuthConfig
from pydantic import Field


class _AuthFiefConfig(AuthConfig):
    base_url: str = Field(description="Base URL of Fief tenant")
    callback_url: str = Field(description="URL of the callback route", default="")
    client_id: str = Field(description="ID of Fief client")
    client_secret: str = Field(description="Secret of Fief client")
    admin_api_key: str = Field(description="Admin API key", default="")
    oauth_provider_id: str = Field(description="OAuth provider ID", default="")
