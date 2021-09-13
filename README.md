[![Build Status](https://github.com/davidbrochart/jupyverse/workflows/CI/badge.svg)](https://github.com/davidbrochart/jupyverse/actions)
[![Code style: black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Binder](https://mybinder.org/badge_logo.svg)](https://mybinder.org/v2/gh/davidbrochart/jupyverse/HEAD?filepath=examples%2Fjupyverse.ipynb)

# jupyverse

A set of [FPS](https://github.com/adriendelsalle/fps) plugins implementing a Jupyter server.

## Install

```bash
pip install jupyverse[jupyterlab]
```

Note: at this stage of development, it is preferable to install from sources (see below).

## Development install

Clone this repository and install the needed plugins:

```bash
pip install -e .[jupyterlab] --no-deps
pip install -e plugins/jupyterlab
pip install -e plugins/contents
pip install -e plugins/kernels
pip install -e plugins/terminals
pip install -e plugins/nbconvert
pip install -e plugins/yjs
pip install -e plugins/auth

# you should also install the latest FPS:
pip install git+https://github.com/adriendelsalle/fps

# if you want RetroLab instead of JupyterLab:
# pip install -e .[retrolab] --no-deps
# pip install -e plugins/retrolab
# ...
```

## Usage

## Without authentication

```bash
jupyverse --open-browser --authenticator.disable_auth=true
```

This will open a browser at http://127.0.0.1:8000 by default, and load the JupyterLab front-end.
You have full access to the API, without restriction.

## With authentication

```bash
jupyverse --open-browser
```

We provide a JupyterLab frontend for authentication, that you can install with:

```bash
pip install git+https://github.com/davidbrochart/jupyverse-auth
```

You can currently authenticate as an anonymous user, or
[using a GitHub account](https://github.com/davidbrochart/jupyverse-auth#authentication-with-github).

## With collaborative editing

```bash
jupyverse --open-browser --JupyterLab.collaborative=true
```

This is especially interesting if you are authenticated, since your will appear as the identity
you chose for authentication.
