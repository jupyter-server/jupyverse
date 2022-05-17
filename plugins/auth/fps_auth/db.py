import secrets
from pathlib import Path
from typing import AsyncGenerator, List

from fastapi import Depends
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTableUUID  # type: ignore
from fastapi_users.db import (  # type: ignore
    SQLAlchemyBaseUserTableUUID,
    SQLAlchemyUserDatabase,
)
from fps.config import get_config  # type: ignore
from sqlalchemy import Boolean, Column, String, Text  # type: ignore
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine  # type: ignore
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base  # type: ignore
from sqlalchemy.orm import relationship, sessionmaker  # type: ignore

from .config import AuthConfig

auth_config = get_config(AuthConfig)

jupyter_dir = Path.home() / ".local" / "share" / "jupyter"
jupyter_dir.mkdir(parents=True, exist_ok=True)
secret_path = jupyter_dir / "jupyverse_secret"
userdb_path = jupyter_dir / "jupyverse_users.db"

if auth_config.clear_users:
    if userdb_path.is_file():
        userdb_path.unlink()
    if secret_path.is_file():
        secret_path.unlink()

if not secret_path.is_file():
    with open(secret_path, "w") as f:
        f.write(secrets.token_hex(32))

with open(secret_path) as f:
    secret = f.read()


DATABASE_URL = f"sqlite+aiosqlite:///{userdb_path}"
Base: DeclarativeMeta = declarative_base()


class OAuthAccount(SQLAlchemyBaseOAuthAccountTableUUID, Base):
    pass


class User(SQLAlchemyBaseUserTableUUID, Base):
    anonymous = Column(Boolean, default=True, nullable=False)
    email = Column(String(length=32), nullable=False, unique=True)
    username = Column(String(length=32), nullable=True, unique=True)
    name = Column(String(length=32), nullable=True)
    color = Column(String(length=32), nullable=True)
    avatar = Column(String(length=32), nullable=True)
    workspace = Column(Text(), default="{}", nullable=False)
    settings = Column(Text(), default="{}", nullable=False)
    oauth_accounts: List[OAuthAccount] = relationship("OAuthAccount", lazy="joined")


engine = create_async_engine(DATABASE_URL)
Session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def create_db_and_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with Session() as session:
        yield session


async def get_user_db(session: AsyncSession = Depends(get_async_session)):
    yield SQLAlchemyUserDatabase(session, User, OAuthAccount)


class UserDb:
    async def __aenter__(self):
        self.session = Session()
        session = await self.session.__aenter__()
        return SQLAlchemyUserDatabase(session, User, OAuthAccount)

    async def __aexit__(self, exc_type, exc_value, exc_tb):
        return await self.session.__aexit__(exc_type, exc_value, exc_tb)
