from fps import Module
from fps_jupyter_server import JupyterServer


class JupyterLabLspModule(Module):
    async def prepare(self) -> None:
        jupyter_server = await self.get(JupyterServer)
        jupyter_server.proxy("/lsp")
