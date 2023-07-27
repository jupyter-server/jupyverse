import os
from urllib.parse import urlparse

from jupyverse_api.cli import main


def launch():
    service_url = os.environ.get("JUPYTERHUB_SERVICE_URL")
    url = urlparse(service_url)
    try:
        return main.callback(
            open_browser=True,
            host=url.hostname,
            port=url.port,
            set_=[
                f"frontend.base_url={url.path}",
                f"app.mount_path={url.path}",
            ],
            disable=[],
        )
    except Exception:
        return
