from typing import Optional

from pydantic import BaseModel


class KernelInfo(BaseModel):
    name: Optional[str] = None
    id: Optional[str] = None


class CreateSession(BaseModel):
    kernel: KernelInfo
    name: str
    path: str
    type: str


class Kernel(BaseModel):
    id: str
    name: str
    last_activity: str
    execution_state: str
    connections: int


class Notebook(BaseModel):
    path: str
    name: str


class Session(BaseModel):
    id: str
    path: str
    name: str
    type: str
    kernel: Kernel
    notebook: Notebook


class Execution(BaseModel):
    document_id: str
    cell_idx: int
