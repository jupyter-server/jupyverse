from fastapi import Request, Response
from fastapi.responses import RedirectResponse


class RedirectException(Exception):
    def __init__(self, redirect_to: str):
        self.redirect_to = redirect_to


async def _redirect_exception_handler(request: Request, exc: RedirectException) -> Response:
    return RedirectResponse(url=exc.redirect_to)
