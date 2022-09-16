import pkg_resources

__version__ = "0.0.41"

auth = {ep.name: ep.load() for ep in pkg_resources.iter_entry_points(group="jupyverse_auth")}

try:
    User = auth["User"]
    current_user = auth["current_user"]
    update_user = auth["update_user"]
    websocket_auth = auth["websocket_auth"]
except KeyError:
    raise RuntimeError(
        "An auth plugin must be installed for Jupyverse to run. For instance: pip install fps-auth"
    )
