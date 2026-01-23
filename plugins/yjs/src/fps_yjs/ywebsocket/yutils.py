from anyio.streams.memory import MemoryObjectSendStream
from pycrdt import TransactionEvent


def put_updates(update_send_stream: MemoryObjectSendStream, event: TransactionEvent) -> None:
    try:
        update = event.update
        update_send_stream.send_nowait(update)
    except Exception:
        pass
