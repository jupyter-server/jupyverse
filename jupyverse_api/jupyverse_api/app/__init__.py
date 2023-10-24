from __future__ import annotations

import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import FastAPI, Request

from ..exceptions import RedirectException, _redirect_exception_handler

logger = logging.getLogger("app")


class App:
    """A wrapper around FastAPI that checks for endpoint path conflicts."""

    _app: FastAPI
    _router_paths: Dict[str, List[str]]

    def __init__(self, app: FastAPI, mount_path: str | None = None):
        if mount_path is None:
            self._app = app
        else:
            subapi = FastAPI()
            app.mount(mount_path, subapi)
            self._app = subapi
        app.add_exception_handler(RedirectException, _redirect_exception_handler)
        self._router_paths = defaultdict(list)
        self._started_time = datetime.now(timezone.utc)
        self._last_activity = self._started_time

        @app.middleware("http")
        async def get_last_activity(request: Request, call_next):
            self._last_activity = datetime.now(timezone.utc)
            return await call_next(request)

    @property
    def started_time(self) -> datetime:
        return self._started_time

    @property
    def last_activity(self) -> datetime:
        return self._last_activity

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

    def add_middleware(self, middleware, *args, **kwargs) -> None:
        self._app.add_middleware(middleware, *args, **kwargs)
