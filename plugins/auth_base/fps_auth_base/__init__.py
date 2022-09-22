import pkg_resources
from fps.logging import get_configured_logger  # type: ignore

__version__ = "0.0.43"

logger = get_configured_logger("auth_base")

auth = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="jupyverse_auth")}

try:
    User = auth["User"]
    current_user = auth["current_user"]
    update_user = auth["update_user"]
    websocket_auth = auth["websocket_auth"]

except KeyError:
    logger.warn("No configured auth, defaulting to noauth.")
    from .backend import current_user  # noqa: F401
    from .backend import update_user  # noqa: F401
    from .backend import websocket_auth  # noqa: F401
    from .models import BaseUser as User  # noqa: F401
