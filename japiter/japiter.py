import typer

from .app import Japiter


cli = typer.Typer()


@cli.command()
def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    routers: str = "",
):
    print(routers)
    Japiter(host, port, routers)


if __name__ == "__main__":
    cli()
