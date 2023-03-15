from pydantic import BaseModel


class JupyterLabConfig(BaseModel):
    dev_mode: bool = False
