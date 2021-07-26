from datetime import datetime, timezone
import hmac
import hashlib
from typing import List, Dict, Tuple, Any, Optional

from zmq.sugar.socket import Socket
from zmq.utils import jsonapi
from dateutil.parser import parse as dateutil_parse  # type: ignore

protocol_version_info = (5, 3)
protocol_version = "%i.%i" % protocol_version_info

DELIM = b"<IDS|MSG>"


def str_to_date(obj: Dict[str, Any]) -> Dict[str, Any]:
    if "date" in obj:
        obj["date"] = dateutil_parse(obj["date"])
    return obj


def date_to_str(obj: Dict[str, Any]):
    if "date" in obj and type(obj["date"]) is not str:
        obj["date"] = obj["date"].isoformat().replace("+00:00", "Z")
    return obj


def utcnow() -> datetime:
    return datetime.utcnow().replace(tzinfo=timezone.utc)


def pack(obj: Dict[str, Any]) -> bytes:
    return jsonapi.dumps(obj)


def unpack(s: bytes) -> Dict[str, Any]:
    return jsonapi.loads(s)


def sign(msg_list: List[bytes], key: str) -> bytes:
    auth = hmac.new(key.encode("ascii"), digestmod=hashlib.sha256)
    h = auth.copy()
    for m in msg_list:
        h.update(m)
    return h.hexdigest().encode()


def serialize(msg: Dict[str, Any], key: str) -> List[bytes]:
    message = [
        pack(date_to_str(msg["header"])),
        pack(date_to_str(msg["parent_header"])),
        pack(date_to_str(msg["metadata"])),
        pack(date_to_str(msg.get("content", {}))),
    ]
    to_send = [DELIM, sign(message, key)] + message
    return to_send


def deserialize(msg_list: List[bytes]) -> Dict[str, Any]:
    message: Dict[str, Any] = {}
    header = unpack(msg_list[1])
    message["header"] = str_to_date(header)
    message["msg_id"] = header["msg_id"]
    message["msg_type"] = header["msg_type"]
    message["parent_header"] = str_to_date(unpack(msg_list[2]))
    message["metadata"] = unpack(msg_list[3])
    message["content"] = unpack(msg_list[4])
    message["buffers"] = [memoryview(b) for b in msg_list[5:]]
    return message


def feed_identities(msg_list: List[bytes]) -> Tuple[List[bytes], List[bytes]]:
    idx = msg_list.index(DELIM)
    return msg_list[:idx], msg_list[idx + 1 :]  # noqa


def send_message(msg: Dict[str, Any], sock: Socket, key: str) -> None:
    to_send = serialize(msg, key)
    sock.send_multipart(to_send, copy=True)


async def receive_message(
    sock: Socket, timeout: float = float("inf")
) -> Optional[Dict[str, Any]]:
    timeout *= 1000  # in ms
    ready = await sock.poll(timeout)
    if ready:
        msg_list = await sock.recv_multipart()
        idents, msg_list = feed_identities(msg_list)
        return deserialize(msg_list)
    return None
