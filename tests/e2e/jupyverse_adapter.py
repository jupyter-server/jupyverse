import json
import urllib
from websocket import create_connection
import uuid
import requests
import structlog
from typing import TypeAlias

logger = structlog.get_logger()

KernelId: TypeAlias = str
SessionId: TypeAlias = str


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

    def kernel_info_request(self, kernel_id: KernelId, session_id: SessionId) -> str:
        session_id = str(uuid.uuid4())
        ws = create_connection(
            f"ws://{self.__netloc}/api/kernels/{kernel_id}/channels?session_id={session_id}"
        )
        while True:
            ws.send(
                json.dumps(
                    {
                        "channel": "shell",
                        "header": {
                            "date": "2025-03-07T18:09:53.949Z",
                            "msg_id": "45331fc8-21fa-49b1-b115-4153c6af9df1",
                            "msg_type": "kernel_info_request",
                            "session": session_id,
                            "username": "",
                            "version": "5.2",
                        },
                        "parent_header": {},
                        "metadata": {},
                        "content": {},
                    }
                )
            )
            msg = json.loads(ws.recv())
            if msg["header"]["msg_type"] == "kernel_info_reply":
                break
        ws.close()

    def stop_kernel(self, kernel_id: KernelId):
        response = requests.delete(f"http://{self.__netloc}/api/kernels/{kernel_id}")
        response.raise_for_status()
        logger.info("Stopped kernel %s.", kernel_id)
