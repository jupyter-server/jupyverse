from typing import List, Tuple

import pkg_resources
import rich_click as click
from asphalt.core.cli import run


@click.command()  # type: ignore
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
    open_browser: bool = False,
    host: str = "127.0.0.1",
    port: int = 8000,
    set_: Tuple[str, ...] = (),
    disable: Tuple[str, ...] = (),
    allow_origin: Tuple[str, ...] = (),
) -> None:
    set_list: List[str] = list(set_)
    for i, s in enumerate(set_list):
        set_list[i] = f"component.components.{s}"
    set_list.append(f"component.open_browser={open_browser}")
    set_list.append(f"component.host={host}")
    set_list.append(f"component.port={port}")
    set_list.append(f"component.allow_origin={allow_origin}")
    config = get_config(disable)
    run.callback(
        unsafe=False,
        loop=None,
        set_=set_list,
        service=None,
        configfile=[config],
    )  # type: ignore


def get_config(disable: Tuple[str, ...]) -> str:
    jupyverse_components = [
        ep.name
        for ep in pkg_resources.iter_entry_points(group="jupyverse.components")
        if ep.name not in disable
    ]

    config = ["component:\n  type: jupyverse\n  components:\n"]
    for component in jupyverse_components:
        config.append(f"    {component}:\n      type: {component}\n")

    config.append(
        """
logging:
  version: 1
  disable_existing_loggers: false
  formatters:
    default:
      format: '[%(asctime)s %(levelname)s] %(message)s'
  handlers:
    console:
      class: logging.StreamHandler
      formatter: default
  root:
    handlers: [console]
    level: INFO
  loggers:
    webnotifier:
      level: DEBUG
        """
    )

    config_str = "".join(config)
    return config_str
