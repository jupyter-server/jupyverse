import logging
from collections import defaultdict
from typing import Dict, List

from fastapi import FastAPI

from ..exceptions import RedirectException, _redirect_exception_handler


logger = logging.getLogger("app")


class App:
    """A wrapper around FastAPI that checks for endpoint path conflicts."""

    _app: FastAPI
    _router_paths: Dict[str, List[str]]

    def __init__(self, app: FastAPI):
        self._app = app
        app.add_exception_handler(RedirectException, _redirect_exception_handler)
        self._router_paths = defaultdict(list)

    @property
    def _paths(self):
        return [path for router, paths in self._router_paths.items() for path in paths]

    def _include_router(self, router, _type, **kwargs) -> None:
        new_paths = []
        for route in router.routes:
            path = kwargs.get("prefix", "") + route.path
            for _router, _paths in self._router_paths.items():
                if path in _paths:
                    raise RuntimeError(
                        f"{_type} adds a handler for a path that is already defined in "
                        f"{_router}: {path}"
                    )
            logger.debug("%s added handler for path: %s", _type, path)
            new_paths.append(path)
        self._router_paths[_type].extend(new_paths)
        self._app.include_router(router, **kwargs)

    def _mount(self, path: str, _type, *args, **kwargs) -> None:
        for _router, _paths in self._router_paths.items():
            if path in _paths:
                raise RuntimeError(
                    f"{_type } mounts a path that is already defined in {_router}: {path}"
                )
        self._router_paths[_type].append(path)
        logger.debug("%s mounted path: %s", _type, path)
        self._app.mount(path, *args, **kwargs)
