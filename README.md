# jupyverse

A web server for Jupyter, based on FastAPI.

## Install

For now, the only supported JupyterLab distribution is
[retrolab](https://github.com/jupyterlab/retrolab), so it must also be installed.

```bash
pip install jupyverse retrolab
```

## Usage

Just enter in a terminal:

```bash
jupyverse
```

This will open a browser at http://127.0.0.1:8000 by default, landing on the tree view of RetroLab.
For other options, see ``jupyverse --help``.
