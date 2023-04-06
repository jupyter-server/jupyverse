The auth plugin has a special place because almost every other plugin depends on it for security reasons. It is possible to use any auth plugin as long as it follows a defined [API](./#api). Jupyverse comes with three auth plugins: [fps-noauth](./#fps-noauth), [fps-auth](./#fps-auth) and [fps-auth-fief](./#fps-auth-fief).

## API

An auth plugin must implement a class that inherits from the `jupyverse_api.Auth` abstract base class. This class must have the following methods:

- `current_user`: a method that optionally takes in required permissions for the HTTP endpoint, and returns a FastAPI dependency for the currently logged in user after checking that they have permissions. The user must have all the required permissions (if any), otherwise a `403` HTTP code is returned.
```py
def current_user(self, permissions: Optional[Dict[str, List[str]]] = None) -> Callable:
    async def _current_user():
        if user_has_permissions(permissions):
            return User(**{"username": "John"})
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    return _current_user
```
- `websocket_auth`: a method that optionally takes in required permissions for the WebSocket endpoint, and returns a FastAPI dependency for a tuple consisting of the WebSocket object and the checked permissions, if the WebSocket is accepted, or `None` if the WebSocket is refused. If the WebSocket is refused, the dependency has to close the connection, otherwise it has to be accepted by the caller. The user must have at least one of the required permissions (if any) for the WebSocket to be accepted.
```py
def websocket_auth(self, permissions: Optional[Dict[str, List[str]]] = None) -> Callable[[], Optional[Tuple[Any, Dict[str, List[str]]]]]:
    async def _websocket_auth(websocket: WebSocket) -> Optional[Tuple[WebSocket, Optional[Dict[str, List[str]]]]]:
        accept_websocket = False
        checked_permissions: Optional[Dict[str, List[str]]] = None
        if SESSION_COOKIE_NAME in websocket._cookies:
            access_token = websocket._cookies[SESSION_COOKIE_NAME]
            if permissions is None:
                accept_websocket = True
            else:
                checked_permissions = {}
                for resource, actions in permissions.items():
                    allowed = checked_permissions[resource] = []
                    for action in actions:
                        if user_has_permission(resource, action):
                            allowed.append(action)
                            accept_websocket = True
        if accept_websocket:
            return websocket, checked_permissions
        else:
            await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
            return None

    return _websocket_auth
```
- `update_user`: a FastAPI dependency for a coroutine that takes in user data to update.
```py
async def update_user(self) -> Callable:
    async def _update_user(data: Dict[str, Any]):
        await update_user_profile(data)

    return _update_user
```

## fps-noauth

`fps-noauth` "implements" an unprotected API.

!!! note
    This can be a security risk! Use it only if you want all endpoints to be accessible by any user.
    Typically, only do that on your personal computer.

## fps-auth

`fps-auth` is a [FastAPI-Users](https://fastapi-users.github.io/fastapi-users)-based solution that includes auth endpoints (registration, etc.) inside Jupyverse, as well as the user database. It is thus perfect if you want Jupyverse to completely "embed" authentication.

## fps-auth-fief

`fps-auth-fief` is a [Fief](https://www.fief.dev)-based solution that runs separately from Jupyverse. It can be hosted in the cloud or locally.
