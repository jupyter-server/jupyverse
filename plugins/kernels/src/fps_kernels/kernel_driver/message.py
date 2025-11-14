from __future__ import annotations

import hashlib
import hmac
import json
from datetime import datetime, timezone
from typing import Any, cast
from uuid import uuid4

from dateutil.parser import parse as dateutil_parse

protocol_version_info = (5, 3)
protocol_version = ".".join(map(str, protocol_version_info))

DELIM = b"<IDS|MSG>"


def feed_identities(msg_list: list[bytes]) -> tuple[list[bytes], list[bytes]]:
    idx = msg_list.index(DELIM)
    return msg_list[:idx], msg_list[idx + 1 :]  # noqa


def str_to_date(obj: dict[str, Any]) -> dict[str, Any]:
    if "date" in obj:
        obj["date"] = dateutil_parse(obj["date"])
    return obj


def date_to_str(obj: dict[str, Any]):
    if "date" in obj and not isinstance(obj["date"], str):
        obj["date"] = obj["date"].isoformat().replace("+00:00", "Z")
    return obj


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def create_message_header(msg_type: str, session_id: str, msg_id: str) -> dict[str, Any]:
    if not session_id:
        session_id = msg_id = uuid4().hex
    else:
        msg_id = f"{session_id}_{msg_id}"
    header = {
        "date": utcnow().isoformat().replace("+00:00", "Z"),
        "msg_id": msg_id,
        "msg_type": msg_type,
        "session": session_id,
        "username": "",
        "version": protocol_version,
    }
    return header


def create_message(
    msg_type: str,
    content: dict = {},
    session_id: str = "",
    msg_id: str = "",
    buffers: list = [],
) -> dict[str, Any]:
    header = create_message_header(msg_type, session_id, msg_id)
    msg = {
        "header": header,
        "msg_id": header["msg_id"],
        "msg_type": header["msg_type"],
        "parent_header": {},
        "content": content,
        "metadata": {},
        "buffers": buffers,
    }
    return msg


def dumps(o: Any, **kwargs) -> bytes:
    """Serialize object to JSON bytes (utf-8).

    Keyword arguments are passed along to :py:func:`json.dumps`.
    """
    return json.dumps(o, **kwargs).encode("utf8")


def loads(s: bytes | str, **kwargs) -> dict | list | str | int | float:
    """Load object from JSON bytes (utf-8).

    Keyword arguments are passed along to :py:func:`json.loads`.
    """
    if isinstance(s, bytes):
        s = s.decode("utf8")
    return json.loads(s, **kwargs)


def pack(obj: dict[str, Any]) -> bytes:
    return dumps(obj)


def unpack(s: bytes) -> dict[str, Any]:
    return cast(dict[str, Any], loads(s))


def sign(msg_list: list[bytes], key: str) -> bytes:
    auth = hmac.new(key.encode("ascii"), digestmod=hashlib.sha256)
    h = auth.copy()
    for m in msg_list:
        h.update(m)
    return h.hexdigest().encode()


def serialize_message(
    msg: dict[str, Any], key: str, change_date_to_str: bool = False
) -> list[bytes]:
    _date_to_str = date_to_str if change_date_to_str else lambda x: x
    message = [
        pack(_date_to_str(msg["header"])),
        pack(_date_to_str(msg["parent_header"])),
        pack(_date_to_str(msg["metadata"])),
        pack(_date_to_str(msg.get("content", {}))),
    ]
    to_send = [DELIM, sign(message, key)] + message + msg.get("buffers", [])
    return to_send


def deserialize_message(
    msg_list: list[bytes],
    parent_header: dict[str, Any] | None = None,
    change_str_to_date: bool = False,
) -> dict[str, Any]:
    _str_to_date = str_to_date if change_str_to_date else lambda x: x
    message: dict[str, Any] = {}
    header = unpack(msg_list[1])
    message["header"] = _str_to_date(header)
    message["msg_id"] = header["msg_id"]
    message["msg_type"] = header["msg_type"]
    if parent_header:
        message["parent_header"] = parent_header
    else:
        message["parent_header"] = _str_to_date(unpack(msg_list[2]))
    message["metadata"] = unpack(msg_list[3])
    message["content"] = unpack(msg_list[4])
    message["buffers"] = [memoryview(b) for b in msg_list[5:]]
    return message
