import secrets
from pathlib import Path

from fastapi_users.db import SQLAlchemyBaseUserTable, SQLAlchemyUserDatabase  # type: ignore
from fastapi_users.db import SQLAlchemyBaseOAuthAccountTable  # type: ignore
from sqlalchemy.ext.declarative import DeclarativeMeta, declarative_base  # type: ignore
from sqlalchemy import Boolean, String, Text, Column  # type: ignore
import sqlalchemy  # type: ignore
import databases  # type: ignore
from fps.config import get_config  # type: ignore

from .config import AuthConfig
from .models import (
    UserDB,
)

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


DATABASE_URL = f"sqlite:///{userdb_path}"

database = databases.Database(DATABASE_URL)

Base: DeclarativeMeta = declarative_base()


class UserTable(Base, SQLAlchemyBaseUserTable):
    anonymous = Column(Boolean, default=True, nullable=False)
    email = Column(String(length=32), nullable=False, unique=True)
    username = Column(String(length=32), nullable=True, unique=True)
    name = Column(String(length=32), nullable=True)
    color = Column(String(length=32), nullable=True)
    avatar = Column(String(length=32), nullable=True)
    workspace = Column(Text(), nullable=False)
    settings = Column(Text(), nullable=False)


class OAuthAccount(SQLAlchemyBaseOAuthAccountTable, Base):
    pass


engine = sqlalchemy.create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)

Base.metadata.create_all(engine)

users = UserTable.__table__
oauth_accounts = OAuthAccount.__table__

user_db = SQLAlchemyUserDatabase(UserDB, database, users, oauth_accounts)


def get_user_db():
    yield user_db
