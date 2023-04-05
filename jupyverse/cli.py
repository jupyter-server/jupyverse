import pkg_resources
from typing import List

import rich_click as click
from asphalt.core.cli import run


jupyverse_components = [
    ep.name for ep in pkg_resources.iter_entry_points(group="jupyverse.components")
]

config = [
    """\
component:
  type: jupyverse
  components:
"""
]

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


@click.command()
@click.option(
    "--set",
    "set_",
    multiple=True,
    type=str,
    help="Set configuration.",
)
def main(
    set_: List[str],
) -> None:
    set_ = list(set_)
    for i, s in enumerate(set_):
        set_[i] = f"component.components.{s}"
    run.callback(
        unsafe=False,
        loop=None,
        set_=set_,
        service=None,
        configfile=[config_str],
    )  # type: ignore
