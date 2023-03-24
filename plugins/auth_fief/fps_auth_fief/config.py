from jupyverse_api.auth import AuthConfig


class _AuthFiefConfig(AuthConfig):
    base_url: str  # Base URL of Fief tenant
    client_id: str  # ID of Fief client
    client_secret: str  # Secret of Fief client
