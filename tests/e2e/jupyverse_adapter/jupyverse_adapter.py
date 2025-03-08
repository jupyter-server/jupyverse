from dataclasses import dataclass
import json
import urllib
from websocket import create_connection
import uuid
import requests
from .ws_messages import get_kernel_info_request, get_execute_request
from .types_ import KernelId, SessionId
import structlog

logger = structlog.get_logger()


@dataclass(frozen=True)
class ExecutionResult:
    result: dict
    stdout: list[str]
    errors: list[str]


class JupyverseAdapter:
    def __init__(self, base_url):
        self.__netloc = urllib.parse.urlparse(base_url).netloc

    def new_session(self) -> KernelId:
        kernel_name = str(uuid.uuid4())
        response = requests.post(
            f"http://{self.__netloc}/api/sessions",
            json={
                "kernel": {"name": "python3"},
                "name": kernel_name,
                "path": kernel_name,
                "type": "console",
            },
        )
        response.raise_for_status()
        response_json = response.json()
        kernel_id = response_json["kernel"]["id"]
        session_id = response_json["id"]
        logger.info("Created kernel %s with new session %s.", kernel_id, session_id)
        return kernel_id, session_id

    def close_session(self, session_id: SessionId):
        response = requests.delete(f"http://{self.__netloc}/api/sessions/{session_id}")
        response.raise_for_status()

    def kernel_info_request(self, kernel_id: KernelId, session_id: SessionId) -> str:
        session_id = str(uuid.uuid4())
        ws = create_connection(
            f"ws://{self.__netloc}/api/kernels/{kernel_id}/channels?session_id={session_id}"
        )
        while True:
            ws.send(get_kernel_info_request(session_id))
            msg = json.loads(ws.recv())
            if msg["header"]["msg_type"] == "kernel_info_reply":
                break
        ws.close()

    def execute_code(
        self, kernel_id: KernelId, session_id: SessionId, code: str
    ) -> ExecutionResult:
        session_id = str(uuid.uuid4())
        ws = create_connection(
            f"ws://{self.__netloc}/api/kernels/{kernel_id}/channels?session_id={session_id}"
        )
        stdout = []
        errors = []
        result = None
        while True:
            ws.send(get_execute_request(session_id, code))
            msg = json.loads(ws.recv())
            if (
                msg["header"]["msg_type"] == "execute_reply"
                and msg["content"]["status"] == "ok"
            ) or (
                msg["header"]["msg_type"] == "status"
                and msg["content"]["execution_state"] == "idle"
            ):
                break
            elif msg["header"]["msg_type"] == "stream":
                stdout.append(msg["content"]["text"])
            elif msg["header"]["msg_type"] == "execute_result":
                result = msg["content"]["data"]
            elif msg["header"]["msg_type"] == "error":
                errors.extend(msg["content"]["traceback"])
        ws.close()
        return ExecutionResult(result, stdout, errors)

    def restart_kernel(self, kernel_id: KernelId):
        response = requests.post(
            f"http://{self.__netloc}/api/kernels/{kernel_id}/restart"
        )
        response.raise_for_status()

    def stop_kernel(self, kernel_id: KernelId):
        response = requests.delete(f"http://{self.__netloc}/api/kernels/{kernel_id}")
        response.raise_for_status()
        logger.info("Stopped kernel %s.", kernel_id)
