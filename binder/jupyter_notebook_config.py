jupyverse_jlab_command = ' '.join([
    'jupyverse',
    '--no-open-browser',
    '--authenticator.mode=noauth',
    '--RetroLab.enabled=false',
    '--JupyterLab.collaborative',
    '--JupyterLab.base_url={base_url}jupyverse-jlab/',
    '--port={port}',
] + ['>jupyverse_jlab.log 2>&1'])


jupyverse_rlab_command = ' '.join([
    'jupyverse',
    '--no-open-browser',
    '--authenticator.mode=noauth',
    '--JupyterLab.enabled=false',
    '--RetroLab.collaborative',
    '--RetroLab.base_url={base_url}jupyverse-rlab/',
    '--port={port}',
] + ['>jupyverse_rlab.log 2>&1'])


c.ServerProxy.servers = {
    'jupyverse-jlab': {
        'command': [
            '/bin/bash', '-c', jupyverse_jlab_command
        ],
        'timeout': 60,
        'absolute_url': False
    },
    'jupyverse-rlab': {
        'command': [
            '/bin/bash', '-c', jupyverse_rlab_command
        ],
        'timeout': 60,
        'absolute_url': False
    },
}

c.NotebookApp.default_url = '/jupyverse-jlab'

import logging
c.NotebookApp.log_level = logging.DEBUG
