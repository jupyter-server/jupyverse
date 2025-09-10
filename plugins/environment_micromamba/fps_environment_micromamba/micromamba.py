from typing import TypedDict
from uuid import uuid4

import anyio
import yaml  # type: ignore[import-untyped]
from anyio import Event, open_process, run_process
from anyio.abc import TaskGroup
from anyio.streams.text import TextReceiveStream

from jupyverse_api.environments import EnvironmentStatus, PackageManager


class EnvironmentType(TypedDict):
    name: str
    status: EnvironmentStatus
    done: Event


class Micromamba(PackageManager):
    def __init__(self, task_group: TaskGroup) -> None:
        self._task_group = task_group
        self._environments: dict[str, EnvironmentType] = {}

    async def delete_environment(self, id: str) -> None:
        name = self._environments[id]["name"]
        cmd = f"micromamba env remove -n {name} --yes"
        await run_process(cmd)

    async def create_environment(self, environment_file_path: str) -> str:
        _id = uuid4().hex
        environment: EnvironmentType = {
            "name": "",
            "status": "environment uninitialized",
            "done": Event(),
        }
        self._environments[_id] = environment
        path = anyio.Path(environment_file_path)
        if not await path.is_file():
            environment["status"] = "environment file not found"
            environment["done"].set()
            return _id
        try:
            env = await path.read_text()
            environment["name"] = yaml.load(env, Loader=yaml.CLoader)["name"]
        except BaseException:
            environment["status"] = "environment file not readable"
            environment["done"].set()
            return _id
        environment["status"] = "environment creation start"
        cmd = "micromamba --help"
        try:
            await run_process(cmd)
        except BaseException:
            environment["status"] = "package manager not found"
            environment["done"].set()
            return _id
        cmd = f"micromamba create -f {environment_file_path} --yes"
        self._task_group.start_soon(self._create_environment, environment, cmd)
        return _id

    async def _create_environment(self, environment, cmd) -> None:
        try:
            await run_process(cmd)
        except BaseException:
            environment["status"] = "environment creation error"
        else:
            environment["status"] = "environment creation success"
        environment["done"].set()

    async def wait_for_environment(self, id: str) -> None:
        await self._environments[id]["done"].wait()

    async def get_status(self, id: str) -> EnvironmentStatus:
        return self._environments[id]["status"]

    async def run_in_environment(self, id: str, command: str) -> int:
        name = self._environments[id]["name"]
        cmd = (
            """bash -c 'eval "$(micromamba shell hook --shell bash)";"""
            + f"micromamba activate {name}; {command}"
            + "' & echo $!"
        )
        process = await open_process(cmd)
        assert process.stdout is not None
        async for text in TextReceiveStream(process.stdout):
            break
        return int(text)
