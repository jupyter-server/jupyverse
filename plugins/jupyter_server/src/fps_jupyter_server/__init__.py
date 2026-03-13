from importlib.metadata import version

from .jupyter_server import JupyterServer as JupyterServer

__version__ = version(__package__)
