import tempfile
from pathlib import Path

import nbconvert
from fastapi.responses import FileResponse
from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.nbconvert import Nbconvert


class _Nbconvert(Nbconvert):
    def __init__(
        self,
        app: App,
        auth: Auth,
    ) -> None:
        super().__init__(app, auth)

    async def get_nbconvert_formats(self):
        return {
            name: {"output_mimetype": nbconvert.exporters.get_exporter(name).output_mimetype}
            for name in nbconvert.exporters.get_export_names()
        }

    async def get_nbconvert_document(
        self,
        format: str,
        path: str,
        download: bool,
        user: User,
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
