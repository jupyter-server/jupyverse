jupyverse_jupyterlab_command = " ".join(
    [
        "jupyverse",
        "--set auth.mode=noauth",
        "--set frontend.collaborative=true",
        "--set frontend.base_url={base_url}jupyverse-jupyterlab/",
        "--disable notebook",
        "--port={port}",
    ]
    + [">jupyverse_jupyterlab.log 2>&1"]
)


jupyverse_notebook_command = " ".join(
    [
        "jupyverse",
        "--set auth.mode=noauth",
        "--set frontend.collaborative=true",
        "--set frontend.base_url={base_url}jupyverse-notebook/",
        "--disable jupyterlab",
        "--port={port}",
    ]
    + [">jupyverse_notebook.log 2>&1"]
)


c.ServerProxy.servers = {
    "jupyverse-jupyterlab": {
        "command": ["/bin/bash", "-c", jupyverse_jupyterlab_command],
        "timeout": 60,
        "absolute_url": False,
    },
    "jupyverse-notebook": {
        "command": ["/bin/bash", "-c", jupyverse_notebook_command],
        "timeout": 60,
        "absolute_url": False,
    },
}

c.NotebookApp.default_url = "/jupyverse-jupyterlab"

import logging

c.NotebookApp.log_level = logging.DEBUG
