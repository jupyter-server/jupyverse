[FPS](https://github.com/jupyter-server/fps) is the system used in Jupyverse to extend its functionality. Actually, Jupyverse is just a collection of FPS plugins that together implement a Jupyter server.

In Jupyverse, each plugin is quite independant, except that they all depend on the auth plugin. This is because almost every endpoint has to be protected one way or another.

## Jupyverse extensions

You can extend Jupyverse by creating an FPS plugin. FPS plugins can have configuration and router endpoints that must be registered in entry point groups `fps_config` and `fps_router`, respectively. In a `setup.cfg` file, that would look like the following:
```
[options.entry_points]
fps_config =
    fps-myextension = fps_myextension.config
fps_router =
    fps-myextension = fps_myextension.routes
```
Where `fps-myextension` is the name of your plugin (the `fps-` prefix will automatically be striped).

The configuration will live in `fps_myextension/config.py`, and will look like:
```py
from fps.config import PluginModel
from fps.hooks import register_config

class MyConfig(PluginModel):
    my_param1: str = ""
    my_param2: int = 0

c = register_config(MyConfig)
```
The router will live in `fps_myextension/routes.py`, and will look like:
```py
from fastapi import APIRouter
from fps.hooks import register_router

router = APIRouter()

@router.get("/myendpoint")
def read_endpoint():
    return {"Hello": "World"}

r = register_router(router)
```
That's it! You just need to install this Python package and it will automatically be discovered by FPS at run-time. The `/myendpoint` endpoint will be added to Jupyverse, and you can configure your plugin e.g. at the CLI with:
```bash
jupyverse --myextension.my_param2=3
```
