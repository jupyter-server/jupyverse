from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import RedirectResponse
from fps.hooks import register_router

from .backend import SESSION_COOKIE_NAME, fief

router = APIRouter()


@router.get("/auth-callback", name="auth_callback")
async def auth_callback(request: Request, response: Response, code: str = Query(...)):
    redirect_uri = request.url_for("auth_callback")
    tokens, _ = await fief.auth_callback(code, redirect_uri)

    response = RedirectResponse(request.url_for("root"))
    response.set_cookie(
        SESSION_COOKIE_NAME,
        tokens["access_token"],
        max_age=tokens["expires_in"],
        httponly=True,
        secure=False,
    )

    return response


r = register_router(router)
