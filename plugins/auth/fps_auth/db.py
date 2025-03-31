import secrets
from collections.abc import AsyncGenerator
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Depends
from fastapi_users.db import (
    SQLAlchemyBaseOAuthAccountTableUUID,
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from sqlalchemy import JSON, Boolean, Column, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship

from .config import _AuthConfig


class Base(AsyncAttrs, DeclarativeBase):
    pass


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    anonymous = Column(Boolean, default=True, nullable=False)
    username = Column(String(length=32), nullable=False, unique=True)
    name = Column(String(length=32), default="")
    display_name = Column(String(length=32), default="")
    initials = Column(String(length=8), nullable=True)
    color = Column(String(length=32), nullable=True)
    avatar_url = Column(String(length=32), nullable=True)
    workspace = Column(Text(), default="{}", nullable=False)
    settings = Column(Text(), default="{}", nullable=False)
    permissions = Column(JSON, default={}, nullable=False)
    oauth_accounts: Mapped[list[OAuthAccount]] = relationship("OAuthAccount", lazy="joined")


@dataclass
class Res:
    User: Any
    async_session_maker: Any
    create_db_and_tables: Any
    get_async_session: Any
    get_user_db: Any
    secret: Any


def get_db(auth_config: _AuthConfig) -> Res:
    jupyter_dir = (
        Path.home() / ".local" / "share" / "jupyter"
        if auth_config.directory is None
        else Path(auth_config.directory)
    )
    jupyter_dir.mkdir(parents=True, exist_ok=True)
    name = "jupyverse"
    if auth_config.test:
        name += "_test"
    secret_path = jupyter_dir / f"{name}_secret"
    userdb_path = jupyter_dir / f"{name}_users.db"

    if auth_config.clear_users:
        if userdb_path.is_file():
            userdb_path.unlink()
        if secret_path.is_file():
            secret_path.unlink()
    if auth_config.mode == "token":
        if secret_path.is_file():
            secret_path.unlink()

    if not secret_path.is_file():
        secret_path.write_text(secrets.token_hex(32))

    secret = secret_path.read_text()

    database_url = f"sqlite+aiosqlite:///{userdb_path}"

    engine = create_async_engine(database_url)
    async_session_maker = async_sessionmaker(engine, expire_on_commit=False)

    async def create_db_and_tables():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
        async with async_session_maker() as session:
            yield session

    async def get_user_db(session: AsyncSession = Depends(get_async_session)):
        yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

    return Res(
        User=User,
        async_session_maker=async_session_maker,
        create_db_and_tables=create_db_and_tables,
        get_async_session=get_async_session,
        get_user_db=get_user_db,
        secret=secret,
    )
