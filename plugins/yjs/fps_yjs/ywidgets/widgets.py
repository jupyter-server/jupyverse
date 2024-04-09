import sys
from typing import Any

from pycrdt import TransactionEvent

try:
    from ypywidgets.utils import (  # type: ignore
        YMessageType,
        YSyncMessageType,
        create_update_message,
        process_sync_message,
        sync,
    )
    ypywidgets_installed = True
except ImportError:
    ypywidgets_installed = False

if sys.version_info < (3, 10):
    from importlib_metadata import entry_points
else:
    from importlib.metadata import entry_points


Widgets: Any

if ypywidgets_installed:
    class Widgets:  # type: ignore
        def __init__(self):
            self.ydocs = {
                ep.name: ep.load() for ep in entry_points(group="ypywidgets")
            }
            self.widgets = {}

        def comm_open(self, msg, comm) -> None:
            target_name = msg["content"]["target_name"]
            if target_name != "ywidget":
                return

            name = msg["metadata"]["ymodel_name"]
            comm_id = msg["content"]["comm_id"]
            self.comm = comm
            model = self.ydocs[f"{name}Model"]()
            self.widgets[comm_id] = {"model": model, "comm": comm}
            msg = sync(model.ydoc)
            comm.send(**msg)

        def comm_msg(self, msg) -> None:
            comm_id = msg["content"]["comm_id"]
            message = bytes(msg["buffers"][0])
            if message[0] == YMessageType.SYNC:
                ydoc = self.widgets[comm_id]["model"].ydoc
                reply = process_sync_message(
                    message[1:],
                    ydoc,
                )
                if reply:
                    self.widgets[comm_id]["comm"].send(buffers=[reply])
                if message[1] == YSyncMessageType.SYNC_STEP2:
                    ydoc.observe(self._send)

        def _send(self, event: TransactionEvent):
            update = event.update  # type: ignore
            message = create_update_message(update)
            try:
                self.comm.send(buffers=[message])
            except Exception:
                pass
else:
    Widgets = None
