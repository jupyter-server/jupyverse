from typing import Any, Callable, Dict, List, Optional, Tuple

from jupyverse_api import Config


class Auth:
    @property
    def User(self):
        raise RuntimeError("Auth.User not implemented")

    def current_user(self) -> Callable:
        raise RuntimeError("Auth.current_user not implemented")

    def update_user(self) -> Callable:
        raise RuntimeError("Auth.update_user not implemented")

    def websocket_auth(
        self,
        permissions: Optional[Dict[str, List[str]]] = None,
    ) -> Callable[[], Tuple[Any, Dict[str, List[str]]]]:
        raise RuntimeError("Auth.websocket_auth not implemented")


class AuthConfig(Config):
    pass


# class Auth(metaclass=ABCMeta):
#
#     @property
#     @abstractmethod
#     def User(self):
#         ...
#
#     @abstractmethod
#     def current_user(self) -> Callable:
#         ...
#
#     @abstractmethod
#     def update_user(self) -> Callable:
#         ...
#
#     @abstractmethod
#     def websocket_auth(
#         self,
#         permissions: Optional[Dict[str, List[str]]] = None,
#     ) -> Callable[[], Tuple[Any, Dict[str, List[str]]]]:
#         ...
