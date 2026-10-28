import ghostty
import pytest
from anyio import Event, create_task_group, fail_after, sleep, sleep_forever


class WebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


async def wait_for(predicate):
    with fail_after(2):
        while not predicate():
            await sleep(0)


@pytest.fixture
async def make_output():
    from fps_terminals.output import TerminalOutput

    outputs = []

    async def sender(output, websocket, *, task_status):
        async with create_task_group() as connection:
            await connection.start(output.send, websocket, connection.cancel_scope)
            task_status.started()
            await sleep_forever()

    async with create_task_group() as tasks:

        def factory():
            output = TerminalOutput(lambda websocket: output.detach(websocket))
            outputs.append(output)
            setup = output.setup

            async def attach(websocket):
                await setup(websocket)
                await tasks.start(sender, output, websocket)
                await wait_for(lambda: bool(websocket.messages))

            output.setup = attach
            return output

        try:
            yield factory
        finally:
            for output in outputs:
                output.close()
            tasks.cancel_scope.cancel()


@pytest.mark.anyio
async def test_snapshot_then_live_output(make_output):
    output = make_output()
    try:
        output.resize(20, 5)
        await output.feed("\x1b[31mbefore\x1b[0m\r\n")
        websocket = WebSocket()
        await output.setup(websocket)
        await output.feed("while attaching\r\n")
        assert websocket.messages == [["setup", {}]]
        async with output.lock:
            await output.restore(websocket)
        await output.feed("live")
        await wait_for(lambda: len(websocket.messages) == 3)
        with ghostty.Terminal(20, 5) as restored:
            for kind, text in websocket.messages[1:]:
                assert kind == "stdout"
                restored.feed(text)
            assert restored.contents() == output.emulator.contents()
            assert restored.cursor == output.emulator.cursor
            assert restored.style(0, 0)["fg"] == ("palette", 1)
    finally:
        output.close()


@pytest.mark.anyio
async def test_output_cannot_overtake_snapshot(make_output):
    output = make_output()
    entered, release, finished = Event(), Event(), Event()

    class SlowWebSocket(WebSocket):
        async def send_json(self, message):
            if message[0] == "stdout" and not entered.is_set():
                entered.set()
                await release.wait()
            await super().send_json(message)

    websocket = SlowWebSocket()

    async def restore():
        async with output.lock:
            await output.restore(websocket)

    async def feed():
        await output.feed("live")
        finished.set()

    try:
        await output.feed("before")
        await output.setup(websocket)
        with fail_after(5):
            async with create_task_group() as tasks:
                tasks.start_soon(restore)
                await entered.wait()
                tasks.start_soon(feed)
                await finished.wait()
                assert websocket.messages == [["setup", {}]]
                release.set()
                await wait_for(lambda: websocket.messages[-1] == ["stdout", "live"])
        assert websocket.messages[-1] == ["stdout", "live"]
        with ghostty.Terminal() as restored:
            for _, text in websocket.messages[1:]:
                restored.feed(text)
            assert restored.contents() == "beforelive"
    finally:
        output.close()


@pytest.mark.anyio
async def test_continuation_overflow_defers_only_new_client(make_output):
    output = make_output()
    output.emulator.close()
    output.emulator = ghostty.Terminal(continuation_limit=4)
    first, reconnected = WebSocket(), WebSocket()
    try:
        await output.setup(first)
        async with output.lock:
            await output.restore(first)
        await output.feed("\x1b]2;unfinished title")
        await output.setup(reconnected)
        async with output.lock:
            await output.restore(reconnected)
        assert reconnected.messages == [["setup", {}]]
        await output.feed("\x07done")
        await wait_for(lambda: first.messages[-1] == ["stdout", "\x07done"])
        await wait_for(lambda: len(reconnected.messages) == 2)
        assert first.messages[-1] == ["stdout", "\x07done"]
        assert len(reconnected.messages) == 2
        with ghostty.Terminal() as restored:
            restored.feed(reconnected.messages[1][1])
            assert restored.contents() == "done"
    finally:
        output.close()


@pytest.mark.anyio
async def test_json_snapshot_between_utf8_reads(make_output):
    import codecs

    output = make_output()
    decoder = codecs.getincrementaldecoder("utf-8")(errors="replace")
    websocket = WebSocket()
    try:
        await output.feed(decoder.decode(b"before\xe6"))
        await output.setup(websocket)
        async with output.lock:
            await output.restore(websocket)
        await output.feed(decoder.decode(b"\x97\xa5after"))
        await wait_for(lambda: len(websocket.messages) == 3)
        with ghostty.Terminal() as restored:
            for _, text in websocket.messages[1:]:
                restored.feed(text)
            assert restored.contents() == "before日after"
    finally:
        output.close()


@pytest.mark.anyio
async def test_slow_client_does_not_block_healthy_client(monkeypatch, make_output):
    from anyio import sleep_forever
    from fps_terminals import output as module

    monkeypatch.setattr(module, "SEND_TIMEOUT", 0.02)

    class StalledWebSocket(WebSocket):
        async def send_json(self, message):
            if message[0] == "stdout":
                await sleep_forever()
            await super().send_json(message)

        async def close(self, code):
            self.close_code = code

    output = make_output()
    stalled, healthy = StalledWebSocket(), WebSocket()
    try:
        for websocket in (stalled, healthy):
            await output.setup(websocket)
            output._ready.add(websocket)
        with fail_after(1):
            await output.feed("first")
            await output.feed("second")
        await wait_for(lambda: hasattr(stalled, "close_code"))
        await wait_for(lambda: healthy.messages[-1] == ["stdout", "second"])
        assert stalled not in output.websockets
        assert stalled.close_code == 1013
        assert healthy.messages[-2:] == [["stdout", "first"], ["stdout", "second"]]
        assert output.emulator.contents() == "firstsecond"
    finally:
        output.close()


@pytest.mark.anyio
async def test_snapshot_chunks_preserve_unicode_and_state(monkeypatch, make_output):
    from fps_terminals import output as module

    monkeypatch.setattr(module, "OUTPUT_CHUNK", 64)
    output = make_output()
    websocket = WebSocket()
    try:
        await output.feed(("日😀\r\n" * 100) + "\x1b[31mend")
        await output.setup(websocket)
        async with output.lock:
            await output.restore(websocket)
        snapshot = output.emulator.serialize().decode("utf-8")
        await wait_for(
            lambda: (
                sum(len(text) for kind, text in websocket.messages if kind == "stdout")
                == len(snapshot)
            )
        )
        chunks = [text for kind, text in websocket.messages if kind == "stdout"]
        assert len(chunks) > 1
        assert all(len(chunk) <= 64 for chunk in chunks)
        with ghostty.Terminal() as restored:
            for chunk in chunks:
                chunk.encode("utf-8")  # Each JSON string contains whole Unicode characters.
                restored.feed(chunk)
            assert restored.contents() == output.emulator.contents()
            assert restored.cursor == output.emulator.cursor
    finally:
        output.close()


@pytest.mark.anyio
async def test_full_queue_disconnects_only_lagging_client(monkeypatch, make_output):
    from fps_terminals import output as module

    monkeypatch.setattr(module, "OUTPUT_QUEUE_SIZE", 4)
    monkeypatch.setattr(module, "SEND_TIMEOUT", 10)
    entered = Event()

    class StalledWebSocket(WebSocket):
        async def send_json(self, message):
            if message[0] == "stdout":
                entered.set()
                await sleep_forever()
            await super().send_json(message)

        async def close(self, code):
            self.close_code = code

    output = make_output()
    stalled, healthy = StalledWebSocket(), WebSocket()
    try:
        for websocket in (stalled, healthy):
            await output.setup(websocket)
            output._ready.add(websocket)
        await output.feed("start")
        await entered.wait()
        await wait_for(lambda: healthy.messages[-1] == ["stdout", "start"])
        with fail_after(1):
            for index in range(5):
                text = str(index)
                await output.feed(text)
                await wait_for(lambda: healthy.messages[-1] == ["stdout", text])
            await wait_for(lambda: hasattr(stalled, "close_code"))
        assert stalled.close_code == 1013
        assert stalled not in output.websockets
        assert healthy in output.websockets
        assert output.emulator.contents() == "start01234"
    finally:
        output.close()


@pytest.mark.anyio
async def test_unfinished_control_sequence_restore_expires(monkeypatch, make_output):
    from anyio import sleep_forever
    from fastapi import WebSocketDisconnect
    from fps_terminals import output as module

    monkeypatch.setattr(module, "RESTORE_TIMEOUT", 0.02)

    class IdleWebSocket(WebSocket):
        async def receive_json(self):
            await sleep_forever()

        async def close(self, code):
            self.close_code = code

    output = make_output()
    output.emulator.close()
    output.emulator = ghostty.Terminal(continuation_limit=4)
    websocket = IdleWebSocket()
    try:
        await output.feed("\x1b]2;unfinished title")
        await output.setup(websocket)
        async with output.lock:
            await output.restore(websocket)
        with fail_after(1), pytest.raises(WebSocketDisconnect):
            await output.receive(websocket)
        await wait_for(lambda: hasattr(websocket, "close_code"))
        assert websocket.close_code == 1013
        assert websocket not in output.websockets
    finally:
        output.close()


@pytest.mark.parametrize(
    "columns, rows",
    [(65535, 65535), (501, 24), (80, 501), (500, 500), (0, 24), (-1, 24), (80.0, 24), (True, 24)],
)
@pytest.mark.anyio
async def test_unsafe_dimensions_rejected(columns, rows, make_output):
    from fps_terminals.output import valid_size

    output = make_output()
    try:
        assert not valid_size(columns, rows)
        with pytest.raises(ValueError):
            output.resize(columns, rows)
        assert output.emulator.size == (80, 24)
    finally:
        output.close()


@pytest.mark.anyio
async def test_completed_restore_does_not_expire_idle_client(monkeypatch, make_output):
    from anyio import create_memory_object_stream, sleep
    from fps_terminals import output as module

    monkeypatch.setattr(module, "RESTORE_TIMEOUT", 0.02)
    send, receive = create_memory_object_stream(1)

    class IdleWebSocket(WebSocket):
        async def receive_json(self):
            return await receive.receive()

        async def close(self, code):
            pytest.fail("A restored client must remain connected")

    output = make_output()
    output.emulator.close()
    output.emulator = ghostty.Terminal(continuation_limit=4)
    websocket = IdleWebSocket()

    async def finish_restoration():
        await sleep(0)
        await output.feed("\x07done")
        # Let the original pending deadline expire before receiving client input.
        await sleep(0.05)
        await send.send(["stdin", "input"])

    try:
        await output.feed("\x1b]2;unfinished title")
        await output.setup(websocket)
        async with output.lock:
            await output.restore(websocket)
        with fail_after(1):
            async with create_task_group() as tasks:
                tasks.start_soon(finish_restoration)
                assert await output.receive(websocket) == ["stdin", "input"]
        assert websocket in output._ready
    finally:
        output.close()
        await send.aclose()
        await receive.aclose()


@pytest.mark.anyio
async def test_snapshot_larger_than_live_queue(monkeypatch, make_output):
    from fps_terminals import output as module

    monkeypatch.setattr(module, "OUTPUT_QUEUE_SIZE", 2)
    monkeypatch.setattr(module, "OUTPUT_CHUNK", 64)
    output = make_output()
    websocket = WebSocket()
    try:
        await output.feed("history\r\n" * 100)
        await output.setup(websocket)
        async with output.lock:
            await output.restore(websocket)
        await output.feed("live")
        await wait_for(lambda: websocket.messages[-1] == ["stdout", "live"])
        assert websocket in output.websockets
        assert len(websocket.messages) > module.OUTPUT_QUEUE_SIZE
        with ghostty.Terminal() as restored:
            for _, text in websocket.messages[1:]:
                restored.feed(text)
            assert restored.contents() == output.emulator.contents()
    finally:
        output.close()


@pytest.mark.anyio
@pytest.mark.parametrize("blocked", [False, True])
async def test_sender_notifies_shutdown_before_cleanup_task(make_output, blocked):
    entered = Event()

    class ClosingWebSocket(WebSocket):
        sending = False
        closed = False

        async def send_json(self, message):
            assert not self.sending
            self.sending = True
            try:
                if blocked and message[0] == "stdout":
                    entered.set()
                    await sleep_forever()
                await super().send_json(message)
            finally:
                self.sending = False

        async def close(self):
            assert not self.sending
            self.closed = True

    output = make_output()
    websocket = ClosingWebSocket()
    try:
        await output.setup(websocket)
        output._ready.add(websocket)
        await output.feed("last output")
        if blocked:
            await entered.wait()
        else:
            await wait_for(lambda: websocket.messages[-1] == ["stdout", "last output"])
        output.close()
        # Force the sender to exit before the terminal's cleanup task runs.
        await wait_for(lambda: websocket.closed)
        with fail_after(1):
            await output.wait_closed()
        assert websocket.messages[-1] == ["disconnect", 1]
        assert websocket not in output.websockets
    finally:
        output.close()
