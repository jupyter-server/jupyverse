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

Then either use `uv` or `pip` to install in development mode.

#### Using `uv`

Install all plugins:

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

#### Using `pip`

Using `pip` sometimes gives more control, for instance if you want to install third-party libraries
in development mode too. It is recommended to create a virtual environment before running the
following commands:

```bash
pip install --group test \
    -e jupyverse_api \
    -e plugins/auth \
    -e plugins/auth_fief \
    -e plugins/auth_jupyterhub \
    -e plugins/contents \
    -e plugins/file_id \
    -e plugins/file_watcher \
    -e plugins/file_watcher_poll \
    -e plugins/frontend \
    -e plugins/jupyterlab \
    -e plugins/kernel_subprocess \
    -e plugins/kernel_web_worker \
    -e plugins/kernels \
    -e plugins/lab \
    -e plugins/login \
    -e plugins/nbconvert \
    -e plugins/noauth \
    -e plugins/notebook \
    -e plugins/resource_usage \
    -e plugins/terminals \
    -e plugins/webdav \
    -e plugins/yjs \
    -e .
```

Run tests with:

```bash
pytest -v
```

Run jupyverse with:

```bash
jupyverse \
    --disable auth_fief \
    --disable auth_jupyterhub \
    --disable noauth \
    --disable file_watcher_poll \
    --disable notebook
```
