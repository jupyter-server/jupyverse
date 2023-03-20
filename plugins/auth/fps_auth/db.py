import logging
import secrets
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID
from fastapi_users.db import (
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from sqlalchemy import JSON, Boolean, Column, String, Text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base
from sqlalchemy.orm import relationship, sessionmaker


logger = logging.getLogger("auth")


class Db:
    def __init__(self, auth_config):
        jupyter_dir = Path.home() / ".local" / "share" / "jupyter"
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

        if not secret_path.is_file():
            secret_path.write_text(secrets.token_hex(32))

        self.secret = secret_path.read_text()

        database_url = f"sqlite+aiosqlite:///{userdb_path}"

        engine = create_async_engine(database_url)
        async_session_maker = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

        async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
            async with async_session_maker() as session:
                yield session

        async def get_user_db(session: AsyncSession = Depends(get_async_session)):
            yield SQLAlchemyUserDatabase(session, User, OAuthAccount)

        async def create_db_and_tables():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

        self.get_async_session = get_async_session
        self.get_user_db = get_user_db
        self.create_db_and_tables = create_db_and_tables


Base: DeclarativeMeta = declarative_base()


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    anonymous = Column(Boolean, default=True, nullable=False)
    email = Column(String(length=32), nullable=False, unique=True)
    username = Column(String(length=32), nullable=False, unique=True)
    name = Column(String(length=32), default="")
    display_name = Column(String(length=32), default="")
    initials = Column(String(length=8), nullable=True)
    color = Column(String(length=32), nullable=True)
    avatar_url = Column(String(length=32), nullable=True)
    workspace = Column(Text(), default="{}", nullable=False)
    settings = Column(Text(), default="{}", nullable=False)
    permissions = Column(JSON, default={}, nullable=False)
    oauth_accounts: List[OAuthAccount] = relationship("OAuthAccount", lazy="joined")
