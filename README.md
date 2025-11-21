[![Build Status](https://github.com/jupyter-server/jupyverse/workflows/test/badge.svg)](https://github.com/jupyter-server/jupyverse/actions)

# Jupyverse

A set of [FPS](https://github.com/jupyter-server/fps) modules implementing a Jupyter server.

Try it online:
- JupyterLab frontend: [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/jupyter-server/jupyverse/HEAD?urlpath=jupyverse-jupyterlab)
- Jupyter Notebook frontend: [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/jupyter-server/jupyverse/HEAD?urlpath=jupyverse-notebook)

Documentation is available [here](https://jupyter-server.github.io/jupyverse).

## Install

### From PyPI

Jupyverse can be installed with `pip`, for instance the following:

```bash
pip install "jupyverse[jupyterlab,auth]"
```

will install jupyverse with the JupyterLab frontend and the [auth](https://github.com/jupyter-server/jupyverse/tree/main/plugins/auth) plugin.

### From conda-forge

Jupyverse can be installed with `micromamba`:

```bash
micromamba create -n jupyverse
micromamba activate jupyverse
micromamba install jupyverse fps-jupyterlab fps-auth
```

### Development install

Clone or fork this repository:

```bash
git clone https://github.com/jupyter-server/jupyverse.git
cd jupyverse
```

Use `uv` to install all plugins:

```bash
uv venv
uv pip install --group test -e ".[ \
    jupyterlab, \
    notebook, \
    auth, \
    auth-fief, \
    auth-jupyterhub, \
    noauth, \
    file-watcher-poll, \
    kernel-web-worker, \
    resource-usage, \
    webdav \
]"
```

Run tests with:

```bash
uv run pytest -v
```

For testing, all the plugins are installed in the same environment. Jupyverse will automatically start all plugins
registered in the `jupyverse.modules` entry point. Some of them should be disabled, for instance there should be only
one authentication plugin:

```bash
uv run jupyverse \
    --disable auth_fief \
    --disable auth_jupyterhub \
    --disable noauth \
    --disable file_watcher_poll \
    --disable notebook
```
