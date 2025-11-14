Jupyverse can be installed to run either [JupyterLab](https://jupyterlab.readthedocs.io) or [Jupyter Notebook](https://jupyter-notebook.readthedocs.io).

## With `pip`

For the JupyterLab frontend:
```bash
pip install "jupyverse[jupyterlab,auth]"
```
Or for the Jupyter Notebook frontend:
```bash
pip install "jupyverse[notebook,auth]"
```

## With `micromamba`

We recommend using `micromamba` to manage [conda-forge](https://conda-forge.org) environments
(see `micromamba`'s
[installation instructions](https://mamba.readthedocs.io/en/latest/installation/micromamba-installation.html)).
First create an environment, here called `jupyverse`, and activate it:
```bash
micromamba create -n jupyverse
micromamba activate jupyverse
```
Then install Jupyverse and the desired plugins.

For the JupyterLab frontend:
```bash
micromamba install -c conda-forge jupyverse fps-jupyterlab fps-auth
```
Or for the Jupyter Notebook frontend:
```bash
micromamba install -c conda-forge jupyverse fps-notebook fps-auth
```

## Development install

You first need to clone the repository:
```bash
git clone https://github.com/jupyter-server/jupyverse.git
cd jupyverse
```
Jupyverse uses [uv](https://docs.astral.sh/uv) for project management. Create a virtual environment and install Jupyverse and all plugins:

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

Tests should be executed using:

```bash
uv run pytest -v
```

As all the plugins are installed in the same environment, you need to disable some of them
in order to start Jupyverse:

```bash
uv run jupyverse \
    --disable auth_fief \
    --disable auth_jupyterhub \
    --disable noauth \
    --disable file_watcher_poll \
    --disable notebook
```
