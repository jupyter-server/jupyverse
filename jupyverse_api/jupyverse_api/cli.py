import json
import sys
from typing import Any, List, Tuple

import rich_click as click
from fps import get_config, get_root_module, merge_config
from fps import main as fps_main

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points


@click.command()  # type: ignore
@click.option(
    "--debug",
    is_flag=True,
    show_default=True,
    default=False,
    help="Enable debug mode.",
)
@click.option(
    "--open-browser",
    is_flag=True,
    show_default=True,
    default=False,
    help="Open a browser window.",
)
@click.option(
    "--host",
    type=str,
    default="127.0.0.1",
    help="The host URL.",
)
@click.option(
    "--port",
    type=int,
    default=8000,
    help="The host port.",
)
@click.option(
    "--query-param",
    multiple=True,
    type=str,
    help='The query parameter key and value, separated by "=".',
)
@click.option(
    "--allow-origin",
    multiple=True,
    type=str,
    help="The origin to allow.",
)
@click.option(
    "--set",
    "set_",
    multiple=True,
    type=str,
    help="Set configuration.",
)
@click.option(
    "--disable",
    multiple=True,
    type=str,
    help="Disable plugin.",
)
def main(
    debug: bool = False,
    open_browser: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000,
    set_: Tuple[str, ...] = (),
    disable: Tuple[str, ...] = (),
    allow_origin: Tuple[str, ...] = (),
    query_param: Tuple[str, ...] = (),
) -> None:
    query_params_dict = {}
    for qp in query_param:
        key, _, value = qp.partition("=")
        query_params_dict[key] = value
    query_params_str = json.dumps(query_params_dict)
    allow_origins_str = json.dumps(allow_origin)
    set_list: List[str] = list(set_)
    set_list.append(f"debug={debug}")
    set_list.append(f"open_browser={open_browser}")
    set_list.append(f"host={host}")
    set_list.append(f"port={port}")
    set_list.append(f"allow_origins={allow_origins_str}")
    set_list.append(f"query_params={query_params_str}")
    fps_main.callback(
        "jupyverse_api.main:JupyverseModule",
        set_=set_list,
    )  # type: ignore
    cli_config = get_config()
    pluggin_config = get_pluggin_config(disable)
    config = merge_config(cli_config, pluggin_config)
    root_module = get_root_module(config)
    root_module.run()


def get_pluggin_config(disable: Tuple[str, ...]) -> dict[str, Any]:
    jupyverse_modules = [
        ep.name
        for ep in entry_points(group="jupyverse.modules")
        if ep.name not in disable
    ]
    config = {
        "root_module": {
            "modules": {
                module: {
                    "type": module
                }
                for module in jupyverse_modules
            }
        }
    }
    return config
