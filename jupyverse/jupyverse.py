import typer

from .app import Jupyverse


cli = typer.Typer()


@cli.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    routers: str = "jupyverse.routers.retro_lab,"
    "jupyverse.routers.contents,"
    "jupyverse.routers.kernels",
):
    Jupyverse(host, port, routers)


if __name__ == "__main__":
    cli()
