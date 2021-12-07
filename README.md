[![Build Status](https://github.com/jupyter-server/jupyverse/workflows/CI/badge.svg)](https://github.com/jupyter-server/jupyverse/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)

# jupyverse

A set of [FPS](https://github.com/jupyter-server/fps) plugins implementing a Jupyter server.

Try it online:
- JupyterLab frontend: [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/jupyter-server/jupyverse/HEAD?urlpath=jupyverse-jlab)
- RetroLab frontend: [![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/jupyter-server/jupyverse/HEAD?urlpath=jupyverse-rlab)


## Motivation

For the motivations behind this project, please refer to this issue in the
[Jupyter server team compass](https://github.com/jupyter-server/team-compass/issues/11).

## Install

```bash
pip install jupyverse[jupyterlab]  # for the JupyterLab front-end
# or
pip install jupyverse[retrolab]  # for the RetroLab front-end
```

Note: you cannot have both the JupyterLab and the RetroLab front-ends enabled at the same time.
When switching e.g. from the JupyterLab to the RetroLab front-end, you need to
`pip uninstall fps-jupyterlab` or launch Jupyverse with `--JupyterLab.enabled=false`.

## Development install

Clone this repository and install the needed plugins:

```bash
pip install -e . --no-deps
pip install -e plugins/jupyterlab
pip install -e plugins/login
pip install -e plugins/auth
pip install -e plugins/contents
pip install -e plugins/kernels
pip install -e plugins/terminals
pip install -e plugins/lab
pip install -e plugins/nbconvert
pip install -e plugins/yjs

# you should also install the latest FPS:
pip install git+https://github.com/jupyter-server/fps

# if you want RetroLab instead of JupyterLab:
# pip install -e . --no-deps
# pip install -e plugins/retrolab
# ...
```

## Usage

## Without authentication

```bash
jupyverse --open-browser --authenticator.mode=noauth
```

This will open a browser at 127.0.0.1:8000 by default, and load the JupyterLab front-end.
You have full access to the API, without restriction.

## With token authentication

```bash
jupyverse --open-browser --authenticator.mode=token
```

This is the default mode, and it corresponds to
[Jupyter Server's token-based authentication](https://jupyter-server.readthedocs.io/en/latest/operators/security.html#security-in-the-jupyter-server).

## With user authentication

```bash
jupyverse --open-browser --authenticator.mode=user
```

We provide a JupyterLab extension for authentication, that you can install with:

```bash
pip install git+https://github.com/davidbrochart/jupyverse-auth
```

You can currently authenticate as an anonymous user, or
[using a GitHub account](https://github.com/davidbrochart/jupyverse-auth#authentication-with-github).

## With collaborative editing

```bash
jupyverse --open-browser --authenticator.collaborative
```

This is especially interesting if you are "user-authenticated", since your will appear as the
identity you chose for authentication.
