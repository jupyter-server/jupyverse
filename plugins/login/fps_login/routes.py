from pathlib import Path
from fastapi import APIRouter
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fps.hooks import register_router  # type: ignore
from fps.logging import get_configured_logger  # type: ignore

logger = get_configured_logger("login")

router = APIRouter()
prefix_static = Path(__file__).parent / "static"

router.mount(
    "/static/login_page",
    StaticFiles(directory=prefix_static),
    name="static",
)


@router.get("/login_page")
async def api_login():
    return FileResponse(prefix_static / "index.html")


r = register_router(router)
