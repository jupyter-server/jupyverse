from sqlalchemy import JSON, Boolean, Column, String, Text
from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase


class Base(AsyncAttrs, DeclarativeBase):
    pass


class UserDB(Base):
    __tablename__ = "user_account"

    token = Column(String(32), primary_key=True)
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
