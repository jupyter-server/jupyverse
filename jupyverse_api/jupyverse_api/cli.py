from __future__ import annotations

import io
import json
from importlib.metadata import entry_points
from typing import Any

import rich_click as click
from fps.cli._cli import main as fps_main


@click.command()  # type: ignore
@click.option(
    "--debug",
    is_flag=True,
    show_default=True,
    default=False,
    help="Enable debug mode.",
)
@click.option(
    "--show-config",
    is_flag=True,
    show_default=True,
    default=False,
    help="Show the actual configuration.",
)
@click.option(
    "--help-all",
    is_flag=True,
    show_default=True,
    default=False,
    help="Show the configuration description.",
)
@click.option(
    "--backend",
    show_default=True,
    default="asyncio",
    help="The name of the event loop to use (asyncio or trio).",
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
@click.option(
    "--timeout",
    type=float,
    default=None,
    help="The timeout for starting Jupyverse.",
)
@click.option(
    "--stop-timeout",
    type=float,
    default=1,
    help="The timeout for stopping Jupyverse.",
)
def main(
    debug: bool = False,
    show_config: bool = False,
    help_all: bool = False,
    backend: str = "asyncio",
    open_browser: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000,
    set_: tuple[str, ...] = (),
    disable: tuple[str, ...] = (),
    allow_origin: tuple[str, ...] = (),
    query_param: tuple[str, ...] = (),
    timeout: float | None = None,
    stop_timeout: float = 1,
) -> None:
    query_params_dict = {}
    for qp in query_param:
        key, _, value = qp.partition("=")
        query_params_dict[key] = value
    query_params_str = json.dumps(query_params_dict)
    allow_origins_str = json.dumps(allow_origin)
    set_list: list[str] = list(set_)
    set_list.append(f"debug={debug}")
    set_list.append(f"open_browser={open_browser}")
    set_list.append(f"host={host}")
    set_list.append(f"port={port}")
    set_list.append(f"allow_origins={allow_origins_str}")
    set_list.append(f"query_params={query_params_str}")
    pluggin_config = io.StringIO(json.dumps(get_pluggin_config(disable)))
    fps_main.callback(
        "",
        set_=set_list,
        config=pluggin_config,
        show_config=show_config,
        help_all=help_all,
        backend=backend,
        timeout=timeout,
        stop_timeout=stop_timeout,
    )  # type: ignore


def get_pluggin_config(disable: tuple[str, ...]) -> dict[str, Any]:
    jupyverse_modules = [
        ep.name for ep in entry_points(group="jupyverse.modules") if ep.name not in disable
    ]
    config = {
        "jupyverse": {
            "type": "jupyverse_api.main:JupyverseModule",
            "modules": {module: {"type": module} for module in jupyverse_modules},
        }
    }
    return config
