import secrets
from pathlib import Path
from typing import Optional

from pydantic import BaseModel
import databases  # type: ignore
import sqlalchemy  # type: ignore
from fastapi_users import models  # type: ignore
from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase  # type: ignore
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTable  # type: ignore
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base  # type: ignore
from sqlalchemy import Boolean, String, Text, Column
from fps.config import Config  # type: ignore

from .config import AuthConfig

auth_config = Config(AuthConfig)


class JupyterUser(BaseModel):
    initialized: bool = False
    anonymous: bool = True
    name: Optional[str] = None
    username: Optional[str] = None
    color: Optional[str] = None
    avatar: Optional[str] = None
    logged_in: bool = False
    workspace: Optional[str] = None
    settings: Optional[str] = None


class User(models.BaseUser, models.BaseOAuthAccountMixin, JupyterUser):
    pass


class UserCreate(models.BaseUserCreate):
    name: Optional[str] = None
    username: Optional[str] = None
    color: Optional[str] = None


class UserUpdate(models.BaseUserUpdate, JupyterUser):
    pass


class UserDB(User, models.BaseUserDB):
    pass


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

DATABASE_URL = f"sqlite:///{userdb_path}"

database = databases.Database(DATABASE_URL)

Base: DeclarativeMeta = declarative_base()


class UserTable(Base, SQLAlchemyBaseUserTable):
    initialized = Column(Boolean, default=False, nullable=False)
    anonymous = Column(Boolean, default=False, nullable=False)
    name = Column(String(length=32), nullable=True)
    username = Column(String(length=32), nullable=True)
    color = Column(String(length=32), nullable=True)
    avatar = Column(String(length=32), nullable=True)
    logged_in = Column(Boolean, default=False, nullable=False)
    workspace = Column(Text(), nullable=True)
    settings = Column(Text(), nullable=True)


class OAuthAccount(SQLAlchemyBaseOAuthAccountTable, Base):
    pass


engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

Base.metadata.create_all(engine)

users = UserTable.__table__
oauth_accounts = OAuthAccount.__table__
user_db = SQLAlchemyUserDatabase(UserDB, database, users, oauth_accounts)
