import json

from .types_ import KernelId, SessionId


def get_kernel_info_request(session_id: SessionId) -> str:
    return json.dumps(
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


def get_execute_request(session_id: SessionId, code: str) -> str:
    return json.dumps(
        {
            "channel": "shell",
            "header": {
                "date": "2025-03-07T18:09:53.949Z",
                "msg_id": "45331fc8-21fa-49b1-b115-4153c6af9df1",
                "msg_type": "execute_request",
                "session": session_id,
                "username": "",
                "version": "5.2",
            },
            "parent_header": {},
            "metadata": {},
            "content": {
                "silent": False,
                "store_history": True,
                "user_expressions": {},
                "allow_stdin": True,
                "stop_on_error": True,
                "code": code,
            },
        }
    )
