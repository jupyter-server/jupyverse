import contextlib

from fps_auth.models import UserCreate, UserUpdate
from fps_auth.config import _AuthConfig
from jupyverse_api.frontend import FrontendConfig
from fps_auth.db import get_db
from fps_auth.backends import get_backend
from rich.console import Console
from rich.table import Table
from sqlalchemy import select


auth_config = _AuthConfig()
frontend_config = FrontendConfig()
db = get_db(auth_config)
backend = get_backend(auth_config, frontend_config, db)

get_async_session_context = contextlib.asynccontextmanager(db.get_async_session)
get_user_db_context = contextlib.asynccontextmanager(db.get_user_db)
get_user_manager_context = contextlib.asynccontextmanager(backend.get_user_manager)


async def get_user_by_email(email):
    async with get_async_session_context() as session:
        async with get_user_db_context(session) as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                return await user_manager.get_by_email(email)


async def delete_user(user):
    async with get_async_session_context() as session:
        async with get_user_db_context(session) as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                return await user_manager.delete(user)


async def create_user(
    username: str, email: str, password: str, is_superuser: bool = False, permissions={}
):
    async with get_async_session_context() as session:
        async with get_user_db_context(session) as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                return await user_manager.create(
                    UserCreate(
                        username=username,
                        email=email,
                        password=password,
                        is_superuser=is_superuser,
                        permissions=permissions,
                    )
                )


async def update_user(user_update: UserUpdate, user, safe: bool = False):
    async with get_async_session_context() as session:
        async with get_user_db_context(session) as user_db:
            async with get_user_manager_context(user_db) as user_manager:
                return await user_manager.update(user_update, user, safe)


async def get_users():
    async with get_async_session_context() as session:
        statement = select(db.User)
        users = (await session.execute(statement)).unique().all()
    return [usr.User for usr in users if usr.User.is_active]


def show_users(users, include_attrs=[], exclude_attrs=[]):
    if include_attrs:
        attrs = include_attrs
    else:
        attrs = [
            "username",
            "name",
            "email",
            "display_name",
            "permissions",
            "anonymous",
            "workspace",
            "settings",
            "avatar_url",
            "color",
            "initials",
            "oauth_accounts",
        ]
        for a in exclude_attrs:
            attrs.remove(a)
    table = Table(title="Users")
    for a in attrs:
        table.add_column(a)
    for user in users:
        table.add_row(*(str(getattr(user, a)) for a in attrs))
    console = Console()
    console.print(table)
