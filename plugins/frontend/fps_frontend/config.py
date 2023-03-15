from jupyverse_api.frontend import FrontendConfig


class _FrontendConfig(FrontendConfig):
    base_url: str = "/"
    collaborative: bool = False
