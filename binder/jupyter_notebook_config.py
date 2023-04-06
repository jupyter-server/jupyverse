jupyverse_jlab_command = " ".join(
    [
        "jupyverse",
        "--set auth.mode=noauth",
        "--set frontend.collaborative=true",
        "--set frontend.base_url={base_url}jupyverse-jlab/",
        "--disable retrolab",
        "--port={port}",
    ]
    + [">jupyverse_jlab.log 2>&1"]
)


jupyverse_rlab_command = " ".join(
    [
        "jupyverse",
        "--set auth.mode=noauth",
        "--set frontend.collaborative=true",
        "--set frontend.base_url={base_url}jupyverse-rlab/",
        "--disable jupyterlab",
        "--port={port}",
    ]
    + [">jupyverse_rlab.log 2>&1"]
)


c.ServerProxy.servers = {
    "jupyverse-jlab": {
        "command": ["/bin/bash", "-c", jupyverse_jlab_command],
        "timeout": 60,
        "absolute_url": False,
    },
    "jupyverse-rlab": {
        "command": ["/bin/bash", "-c", jupyverse_rlab_command],
        "timeout": 60,
        "absolute_url": False,
    },
}

c.NotebookApp.default_url = "/jupyverse-jlab"

import logging

c.NotebookApp.log_level = logging.DEBUG
