import structlog

from jupyverse_api.app import App
from jupyverse_api.auth import Auth, User
from jupyverse_api.environments import (
    CreateEnvironment,
    Environment,
    Environments,
    EnvironmentStatus,
    PackageManager,
)

logger = structlog.get_logger()


class _Environments(Environments):
    def __init__(
        self,
        app: App,
        auth: Auth,
    ) -> None:
        super().__init__(app=app, auth=auth)
        self._package_managers: dict[str, PackageManager] = {}
        self._pm_for_id: dict[str, PackageManager] = {}

    async def delete_environment(
        self,
        id: str,
        user: User,
    ) -> None:
        package_manager = self._pm_for_id[id]
        await package_manager.delete_environment(id)

    async def create_environment(
        self,
        environment: CreateEnvironment,
        user: User,
    ) -> Environment:
        package_manager_name = environment.package_manager_name
        environment_file_path = environment.environment_file_path
        if package_manager_name in self._package_managers:
            logger.info(
                "Creating environment",
                package_manager=package_manager_name,
                environment_file=environment_file_path,
            )
            package_manager = self._package_managers[package_manager_name]
            _id = await package_manager.create_environment(environment_file_path)
            self._pm_for_id[_id] = package_manager
            status = await package_manager.get_status(_id)
            return Environment(id=_id, status=status)
        raise RuntimeError(f"Package manager not found: {package_manager_name}")

    async def wait_for_environment(self, id: str) -> None:
        package_manager = self._pm_for_id[id]
        await package_manager.wait_for_environment(id)

    async def get_status(self, id: str) -> EnvironmentStatus:
        package_manager = self._pm_for_id[id]
        return await package_manager.get_status(id)

    async def run_in_environment(self, id: str, command: str) -> int:
        package_manager = self._pm_for_id[id]
        return await package_manager.run_in_environment(id, command)

    def add_package_manager(self, name: str, package_manager: PackageManager):
        self._package_managers[name] = package_manager
