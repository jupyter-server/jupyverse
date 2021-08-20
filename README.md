# jupyverse

An [FPS](https://github.com/adriendelsalle/fps) plugin implementing a Jupyter server.

## Install

```bash
pip install jupyverse
```

## Development install

Clone this repository and install the needed plugins:

```bash
pip install -e .
pip install -e plugins/auth
pip install -e plugins/contents
pip install -e plugins/kernels
pip install -e plugins/terminals
pip install -e plugins/nbconvert
pip install -e plugins/yjs
pip install -e plugins/jupyterlab

# if you want RetroLab instead of JupyterLab:
# pip install -e plugins/retrolab
```

## Usage

Just enter in a terminal:

```bash
jupyverse
```

This will open a browser at http://127.0.0.1:8000 by default, and load the JupyterLab front-end.
For other options, see ``jupyverse --help``.
