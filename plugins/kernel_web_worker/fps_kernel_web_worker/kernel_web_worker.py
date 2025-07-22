from uuid import uuid4

import pyjs  # type: ignore[import-not-found]
from anyio import TASK_STATUS_IGNORED, Event, create_task_group
from anyio.abc import TaskStatus

from jupyverse_api.kernel import Kernel as Kernel


class KernelWebWorker(Kernel):
    def __init__(self, *args, **kwargs):
        super().__init__()

    async def start(self, *, task_status: TaskStatus[None] = TASK_STATUS_IGNORED) -> None:
        async with (
            self._to_shell_send_stream,
            self._to_shell_receive_stream,
            self._from_shell_send_stream,
            self._from_shell_receive_stream,
            self._to_control_send_stream,
            self._to_control_receive_stream,
            self._from_control_send_stream,
            self._from_control_receive_stream,
            self._to_stdin_send_stream,
            self._to_stdin_receive_stream,
            self._from_stdin_send_stream,
            self._from_stdin_receive_stream,
            self._from_iopub_send_stream,
            self._from_iopub_receive_stream,
            create_task_group() as self.task_group,
        ):
            self.kernel_id = uuid4().hex
            kernel_ready = Event()

            def callback(msg):
                msg_type = msg["type"]
                if msg_type == "started":
                    kernel_ready.set()
                else:
                    msg = [bytes(pyjs.to_py(m)) for m in msg["msg"]]
                    if msg_type == "shell":
                        self.task_group.start_soon(self._from_shell_send_stream.send, msg)
                    elif msg_type == "control":
                        self.task_group.start_soon(self._from_control_send_stream.send, msg)
                    elif msg_type == "stdin":
                        self.task_group.start_soon(self._from_stdin_send_stream.send, msg)
                    elif msg_type == "iopub":
                        self.task_group.start_soon(self._from_iopub_send_stream.send, msg)

            js_callable, self.js_py_object = pyjs.create_callable(callback)
            higher_order_function = pyjs.js.Function(
                "callback", "action", "kernel_id",
                "kernel_web_worker(action, kernel_id, 0, callback);"
            )
            higher_order_function(js_callable, "start", self.kernel_id)
            await kernel_ready.wait()

            self.task_group.start_soon(self.forward_messages_to_shell)
            self.task_group.start_soon(self.forward_messages_to_control)
            self.task_group.start_soon(self.forward_messages_to_stdin)

            task_status.started()
            self.started.set()

    async def stop(self) -> None:
        self.js_py_object.delete()
        self.task_group.cancel_scope.cancel()

    async def interrupt(self) -> None:
        pass

    async def forward_messages_to_shell(self) -> None:
        async for msg in self._to_shell_receive_stream:
            msg = pyjs.to_js(msg)
            pyjs.js.Function(
                "action", "kernel_id", "msg", "kernel_web_worker(action, kernel_id, msg, 0);"
            )("shell", self.kernel_id, msg)

    async def forward_messages_to_control(self) -> None:
        async for msg in self._to_control_receive_stream:
            msg = pyjs.to_js(msg)
            pyjs.js.Function(
                "action", "kernel_id", "msg", "kernel_web_worker(action, kernel_id, msg, 0);"
            )("control", self.kernel_id, msg)

    async def forward_messages_to_stdin(self) -> None:
        async for msg in self._to_stdin_receive_stream:
            msg = pyjs.to_js(msg)
            pyjs.js.Function(
                "action", "kernel_id", "msg", "kernel_web_worker(action, kernel_id, msg, 0);"
            )("stdin", self.kernel_id, msg)
