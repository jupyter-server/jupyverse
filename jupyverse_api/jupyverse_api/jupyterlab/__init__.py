from jupyverse_api import Config, Router


class JupyterLab(Router):
    pass


class JupyterLabConfig(Config):
    dev_mode: bool = False
