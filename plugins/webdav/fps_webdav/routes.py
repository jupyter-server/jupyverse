from __future__ import annotations

import logging
from functools import partial
from pathlib import Path

from asgi_middleware_static_file import ASGIMiddlewareStaticFile  # type: ignore
from asgi_webdav.middleware.cors import ASGIMiddlewareCORS  # type: ignore
from asgi_webdav import __name__ as app_name  # type: ignore
from asgi_webdav import __version__  # type: ignore

try:
    from asgi_webdav.config import (  # type: ignore
        get_config,
        init_config_from_file,
        init_config_from_obj,
    )
    from asgi_webdav.constants import DAV_METHODS, AppEntryParameters  # type: ignore
    from asgi_webdav.server import Server  # type: ignore

    asgi_webdav_installed = True
except BaseException:
    asgi_webdav_installed = False
from jupyverse_api.app import App

from .config import WebDAVConfig


logger = logging.getLogger("webdav")


class WebDAVApp:
    def __init__(self, app, webdav_app):
        self._app = app
        self._webdav_app = webdav_app

    async def __call__(self, scope, receive, send):
        if scope.get("method") in DAV_METHODS and scope.get("path").startswith("/webdav"):
            return await self._webdav_app(scope, receive, send)
        return await self._app(scope, receive, send)


class WebDAV:
    def __init__(self, app: App, webdav_config: WebDAVConfig):
        if not asgi_webdav_installed:
            return

        for account in webdav_config.account_mapping:
            logger.info(f"WebDAV user {account.username} has password {account.password}")
        webdav_conf = webdav_config.dict()
        init_config_from_obj(webdav_conf)
        webdav_aep = AppEntryParameters()
        webdav_app = get_asgi_app(aep=webdav_aep, config_obj=webdav_conf)
        app.add_middleware(partial(WebDAVApp, webdav_app=webdav_app))


# this is to get rid of asgi-webdav's logging configuration, see:
# https://github.com/rexzhang/asgi-webdav/blob/53735fa67030e1db0d610deb58d2ebfedbdd7c3b/asgi_webdav/server.py#L99
def get_asgi_app(aep: AppEntryParameters, config_obj: dict | None = None):
    """create ASGI app"""
    # init config
    if aep.config_file is not None:
        init_config_from_file(aep.config_file)
    if config_obj is not None:
        init_config_from_obj(config_obj)

    config = get_config()
    config.update_from_app_args_and_env_and_default_value(aep=aep)

    # create ASGI app
    app = Server(config)

    # route /_/static
    app = ASGIMiddlewareStaticFile(
        app=app,
        static_url="_/static",
        static_root_paths=[Path(__file__).parent.joinpath("static")],
    )

    # CORS
    if config.cors.enable:
        app = ASGIMiddlewareCORS(
            app=app,
            allow_url_regex=config.cors.allow_url_regex,
            allow_origins=config.cors.allow_origins,
            allow_origin_regex=config.cors.allow_origin_regex,
            allow_methods=config.cors.allow_methods,
            allow_headers=config.cors.allow_headers,
            allow_credentials=config.cors.allow_credentials,
            expose_headers=config.cors.expose_headers,
            preflight_max_age=config.cors.preflight_max_age,
        )

    # config sentry
    if config.sentry_dsn:
        try:
            import sentry_sdk  # type: ignore
            from sentry_sdk.integrations.asgi import SentryAsgiMiddleware  # type: ignore

            sentry_sdk.init(
                dsn=config.sentry_dsn,
                release=f"{app_name}@{__version__}",
            )
            app = SentryAsgiMiddleware(app)

        except ImportError as e:
            logger.warning(e)

    return app
