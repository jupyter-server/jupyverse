Jupyverse can be installed to run either [JupyterLab](https://jupyterlab.readthedocs.io) or [RetroLab](https://github.com/jupyterlab/retrolab).

## With `pip`

For the JupyterLab front-end:
```bash
pip install "jupyverse[jupyterlab,auth]"
```
Or for the RetroLab front-end:
```bash
pip install "jupyverse[retrolab,auth]"
```

## With `mamba`

For the JupyterLab front-end:
```bash
mamba install -c conda-forge jupyverse fps-jupyterlab fps-auth
```
Or for the RetroLab front-end:
```bash
mamba install -c conda-forge jupyverse fps-retrolab fps-auth
```

!!! note
    You cannot have both the JupyterLab and the RetroLab front-ends enabled at the same time.
    When switching e.g. from the JupyterLab to the RetroLab front-end, you need to
    `pip uninstall fps-jupyterlab` or launch Jupyverse with `--jupyterlab.enabled=false`.
    More on that in the [plugins section](../plugins/jupyterlab).

## Development install

You first need to clone the repository:
```bash
git clone https://github.com/jupyter-server/jupyverse.git
cd jupyverse
```

Then install the needed plugins.

- With the [fps-auth](../plugins/auth/#fps-auth) plugin:
```bash
pip install -e plugins/frontend
pip install -e plugins/lab
pip install -e plugins/jupyterlab
pip install -e plugins/login
pip install -e plugins/auth
pip install -e plugins/contents
pip install -e plugins/kernels
pip install -e plugins/terminals
pip install -e plugins/nbconvert
pip install -e plugins/yjs
pip install -e .[test]
```
- With the [fps-auth-fief](../plugins/auth/#fps-auth-fief) plugin:
```bash
pip install -e plugins/frontend
pip install -e plugins/lab
pip install -e plugins/jupyterlab
pip install -e plugins/auth_fief
pip install -e plugins/contents
pip install -e plugins/kernels
pip install -e plugins/terminals
pip install -e plugins/nbconvert
pip install -e plugins/yjs
pip install -e .[test]
```

!!! note
    Same here, you cannot have both the JupyterLab and the RetroLab front-ends enabled at the same time.
    If you want RetroLab instead of JupyterLab, replace the first line with `pip install -e plugins/retrolab`.
