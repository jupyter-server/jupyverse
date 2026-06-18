from collections import defaultdict
from collections.abc import Iterator
from datetime import datetime, timezone
from typing import Any

import structlog
from fastapi import FastAPI, Request, routing

from ..exceptions import RedirectException, _redirect_exception_handler

# public API since FastAPI 0.137.2; None on older versions
iter_route_contexts = getattr(routing, "iter_route_contexts", None)

logger = structlog.get_logger()


def _iter_router_paths(router: Any, prefix: str = "") -> Iterator[str]:
    """Yield the effective paths a router registers, including nested includes.

    Uses the public `iter_route_contexts` when available (FastAPI >= 0.137.2).
    Older versions are handled by walking the routes: plain routes expose
    `path`, while FastAPI 0.137.0/0.137.1 nested includes appear as placeholder
    routes referencing `original_router` / `include_context` and are recursed
    into.
    """
    if iter_route_contexts is not None:
        for context in iter_route_contexts(router.routes):
            yield prefix + (context.path or "")
        return
    for route in router.routes:
        route_path = getattr(route, "path", None)
        if route_path is not None:
            yield prefix + route_path
            continue
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            include_context = getattr(route, "include_context", None)
            nested_prefix = getattr(include_context, "prefix", "") or ""
            yield from _iter_router_paths(original_router, prefix + nested_prefix)


class App:
    """A wrapper around FastAPI that checks for endpoint path conflicts."""

    _app: FastAPI
    _router_paths: dict[str, list[str]]

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
        for path in _iter_router_paths(router, kwargs.get("prefix", "")):
            for _router, _paths in self._router_paths.items():
                if path in _paths:
                    raise RuntimeError(
                        f"{_type} adds a handler for a path that is already defined in "
                        f"{_router}: {path}"
                    )
            logger.debug("Handler added", type=_type, path=path)
            new_paths.append(path)
        self._router_paths[_type].extend(new_paths)
        self._app.include_router(router, **kwargs)

    def _mount(self, path: str, _type, *args, **kwargs) -> None:
        for _router, _paths in self._router_paths.items():
            if path in _paths:
                raise RuntimeError(
                    f"{_type} mounts a path that is already defined in {_router}: {path}"
                )
        self._router_paths[_type].append(path)
        logger.debug("Path mounted", type=_type, path=path)
        self._app.mount(path, *args, **kwargs)

    def add_middleware(self, middleware, *args, **kwargs) -> None:
        self._app.add_middleware(middleware, *args, **kwargs)
