from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

EnvironmentStatus = (
    Literal["package manager not found"]
    | Literal["environment uninitialized"]
    | Literal["environment creation start"]
    | Literal["environment creation success"]
    | Literal["environment creation error"]
    | Literal["environment file not found"]
    | Literal["environment file not readable"]
)


class CreateEnvironment(BaseModel):
    package_manager_name: str
    environment_file_path: str


class Environment(BaseModel):
    id: str
    status: EnvironmentStatus
