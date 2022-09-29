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

Jupyverse uses [Hatch](https://github.com/pypa/hatch) for project management,
hatch can handle multiple environments in parallel allowing for easy development
and testing of different frontends, authentication methods, and incompatible
plugins.

First you should [install Hatch](https://hatch.pypa.io/latest/install/), once it
is installed you can run `hatch env show` to view the available environments.
This will show a table like:

```text
                Standalone
┏━━━━━━━━━┳━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━┓
┃ Name    ┃ Type    ┃ Features ┃ Scripts ┃
┡━━━━━━━━━╇━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━┩
│ default │ virtual │          │         │
├─────────┼─────────┼──────────┼─────────┤
│ docs    │ virtual │ docs     │ build   │
│         │         │          │ serve   │
└─────────┴─────────┴──────────┴─────────┘
                                       Matrices
┏━━━━━━┳━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━┓
┃ Name ┃ Type    ┃ Envs                     ┃ Features ┃ Dependencies    ┃ Scripts   ┃
┡━━━━━━╇━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━┩
│ dev  │ virtual │ dev.jupyterlab-noauth    │ test     │ fastapi>=0.82.0 │ jupyverse │
│      │         │ dev.jupyterlab-auth      │          │                 │ lint      │
│      │         │ dev.jupyterlab-auth_fief │          │                 │ test      │
│      │         │ dev.retrolab-noauth      │          │                 │ typecheck │
│      │         │ dev.retrolab-auth        │          │                 │           │
│      │         │ dev.retrolab-auth_fief   │          │                 │           │
└──────┴─────────┴──────────────────────────┴──────────┴─────────────────┴───────────┘
```

The `default` environment will install all the plugins from pypi, **not** from
the plugin directory, as this is what users get when they install jupyverse. The
`dev` environment installs all plugins in editable mode from the plugin
directory.

Currently the `dev` matrix environment is made up of all combinations of
frontends (`jupyterlab`, `retrolab`) and authentication methods (`noauth`, `auth`,
`auth_fief`), which leads to six combinations.

A number of scripts are available in the dev environments, scripts can be
executed using `hatch run {env}:{script}`, e.g. to serve jupyverse from the
jupyterlab noauth environment use `hatch run dev.jupyterlab-noauth:jupyverse`.

Tests should normally be executed using the `dev.jupyterlab-auth` environment,
e.g. `hatch run dev.jupyterlab-auth:test`.

You can also use the `-e` flag to set an environment, which work with other
commands like shell, so `hatch -e dev.jupyterlab-noauth shell` will spawn a
shell with that environment activated, which is useful for interactive testing
and development.

As the plugins are all installed in editable mode, you could start an instance
of jupyverse in each environment and see how code changes interact with plugins at
the same time.

Finally, `hatch run docs:serve` can be used to view documentation changes.
