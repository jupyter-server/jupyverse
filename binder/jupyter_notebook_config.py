jupyverse_command = ' '.join([
    'jupyverse',
    '--no-open-browser',
    '--authenticator.mode=noauth',
    '--JupyterLab.collaborative',
    '--JupyterLab.base_url={base_url}jupyverse/',
    '--port={port}',
] + ['>jupyverse.log 2>&1'])


c.ServerProxy.servers = {
    'jupyverse': {
        'command': [
            '/bin/bash', '-c', jupyverse_command
        ],
        'timeout': 60,
        'absolute_url': False
    },
}

c.NotebookApp.default_url = '/jupyverse'

import logging
c.NotebookApp.log_level = logging.DEBUG
