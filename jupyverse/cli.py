from .dashboard import Dashboard


def app():
    Dashboard.run(title="Jupyverse Dashboard", log="jupyverse.log")
