from __future__ import annotations

import json
import os
import socket
import tempfile
import uuid
from typing import Union

import zmq
from zmq_anyio import Socket

channel_socket_types = {
    "hb": zmq.REQ,
    "shell": zmq.DEALER,
    "iopub": zmq.SUB,
    "stdin": zmq.DEALER,
    "control": zmq.DEALER,
}

context = zmq.Context()

cfg_t = dict[str, Union[str, int]]


def get_port(ip: str) -> int:
    sock = socket.socket()
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, b"\0" * 8)
    sock.bind((ip, 0))
    port = sock.getsockname()[1]
    sock.close()
    return port


def write_connection_file(
    fname: str = "",
    ip: str = "",
    transport: str = "tcp",
    signature_scheme: str = "hmac-sha256",
    kernel_name: str = "",
) -> tuple[str, cfg_t]:
    ip = ip or "127.0.0.1"

    if not fname:
        fd, fname = tempfile.mkstemp(suffix=".json")
        os.close(fd)
    f = open(fname, "w")

    channels = ["shell", "iopub", "stdin", "control", "hb"]

    cfg: cfg_t = {f"{c}_port": get_port(ip) for c in channels}

    cfg["ip"] = ip
    cfg["key"] = uuid.uuid4().hex
    cfg["transport"] = transport
    cfg["signature_scheme"] = signature_scheme
    cfg["kernel_name"] = kernel_name

    f.write(json.dumps(cfg, indent=2))
    f.close()

    return fname, cfg


def read_connection_file(fname: str) -> cfg_t:
    with open(fname) as f:
        cfg: cfg_t = json.load(f)

    return cfg


def create_socket(channel: str, cfg: cfg_t, identity: bytes | None = None) -> Socket:
    ip = cfg["ip"]
    port = cfg[f"{channel}_port"]
    url = f"tcp://{ip}:{port}"
    socket_type = channel_socket_types[channel]
    sock = Socket(context.socket(socket_type))
    sock.linger = 1000  # set linger to 1s to prevent hangs at exit
    if identity:
        sock.identity = identity
    sock.connect(url)
    return sock


def connect_channel(channel_name: str, cfg: cfg_t, identity: bytes | None = None) -> Socket:
    sock = create_socket(channel_name, cfg, identity)
    if channel_name == "iopub":
        sock.setsockopt(zmq.SUBSCRIBE, b"")
    return sock
