from typing import cast

from fastapi import Request
from fastapi.responses import RedirectResponse


class RedirectException(Exception):
    def __init__(self, redirect_to: str):
        self.redirect_to = redirect_to


async def _redirect_exception_handler(request: Request, exc: Exception) -> RedirectResponse:
    exc = cast(RedirectException, exc)
    return RedirectResponse(url=exc.redirect_to)
