from uuid import uuid4

from pydantic import BaseModel


class Account(BaseModel):
    username: str = uuid4().hex
    password: str = uuid4().hex
    permissions: list[str] = ["+"]


class Provider(BaseModel):
    prefix: str = "/webdav"
    uri: str = "file://."


class WebDAVConfig(BaseModel):
    account_mapping: list[Account] = [Account()]
    provider_mapping: list[Provider] = [Provider()]
