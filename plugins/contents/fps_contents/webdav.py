from asgi_webdav.config import init_config_from_obj  # type: ignore
from asgi_webdav.constants import DAV_METHODS, AppEntryParameters  # type: ignore
from asgi_webdav.server import get_asgi_app as get_webdav_asgi_app  # type: ignore
from fps.hooks import register_application  # type: ignore
from starlette.applications import Starlette

webdav_config = {
    "account_mapping": [{"username": "foo", "password": "bar", "permissions": ["+"]}],
    "provider_mapping": [
        {
            "prefix": "/webdav",
            "uri": "file://.",
        },
    ],
}
init_config_from_obj(webdav_config)
webdav_aep = AppEntryParameters()
webdav_app = get_webdav_asgi_app(aep=webdav_aep, config_obj=webdav_config)


class WebDAVApp(Starlette):
    async def __call__(self, scope, receive, send):
        return await webdav_app.__call__(scope, receive, send)

    def check_scope(self, scope) -> bool:
        if scope.get("method") in DAV_METHODS and scope.get("path").startswith("/webdav"):
            return True
        return False


app = WebDAVApp()

a = register_application(app)
