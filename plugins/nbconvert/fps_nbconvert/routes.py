import tempfile
from pathlib import Path

import nbconvert  # type: ignore
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse
from fps.config import Config  # type: ignore
from fps.hooks import register_router  # type: ignore

from fps_auth.routes import users  # type: ignore
from fps_auth.models import User  # type: ignore
from fps_auth.config import AuthConfig  # type: ignore

router = APIRouter()
auth_config = Config(AuthConfig)


@router.get("/api/nbconvert")
async def get_nbconvert_formats():
    return {
        name: {
            "output_mimetype": nbconvert.exporters.get_exporter(name).output_mimetype
        }
        for name in nbconvert.exporters.get_export_names()
    }


@router.get("/nbconvert/{format}/{path}")
async def get_nbconvert_document(
    format: str,
    path: str,
    download: bool,
    user: User = Depends(users.current_user(optional=auth_config.disable_auth)),
):
    exporter = nbconvert.exporters.get_exporter(format)
    if download:
        media_type = "application/octet-stream"
    else:
        media_type = exporter.output_mimetype
    tmp_dir = Path(tempfile.mkdtemp())
    tmp_path = tmp_dir / (Path(path).stem + exporter().file_extension)
    with open(tmp_path, "wt") as f:
        f.write(exporter().from_filename(path)[0])
    return FileResponse(tmp_path, media_type=media_type, filename=tmp_path.name)


r = register_router(router)
