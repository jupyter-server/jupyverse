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
pip install -e .[jupyterlab]
pip install -e plugins/jupyterlab
pip install -e plugins/contents
pip install -e plugins/kernels
pip install -e plugins/terminals
pip install -e plugins/nbconvert
pip install -e plugins/yjs
pip install -e plugins/auth

# you should also install the latest FPS:
pip install git+https://github.com/adriendelsalle/fps
pip install pluggy==1.0.0.dev0 --force-reinstall

# you must also have the JLab frontend extension for authentication:
pip install git+https://github.com/davidbrochart/jupyverse-auth

# if you want RetroLab instead of JupyterLab:
# pip install -e .[retrolab]
# pip install -e plugins/retrolab
# ...
```

## Usage

Just enter in a terminal:

```bash
jupyverse
```

This will open a browser at http://127.0.0.1:8000 by default, and load the JupyterLab front-end.
For other options, see ``jupyverse --help``.
