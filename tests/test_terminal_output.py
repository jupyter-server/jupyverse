import ghostty
import pytest
from anyio import Event, create_task_group, fail_after


class WebSocket:
    def __init__(self):
        self.messages = []

    async def send_json(self, message):
        self.messages.append(message)


def make_output():
    from fps_terminals.output import TerminalOutput

    output = TerminalOutput(lambda websocket: output.detach(websocket))
    return output


@pytest.mark.anyio
async def test_snapshot_then_live_output():
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
        assert len(websocket.messages) == 3
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
async def test_output_cannot_overtake_snapshot():
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
                assert not finished.is_set()
                release.set()
        assert websocket.messages[-1] == ["stdout", "live"]
        with ghostty.Terminal() as restored:
            for _, text in websocket.messages[1:]:
                restored.feed(text)
            assert restored.contents() == "beforelive"
    finally:
        output.close()


@pytest.mark.anyio
async def test_continuation_overflow_defers_only_new_client():
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
        assert first.messages[-1] == ["stdout", "\x07done"]
        assert len(reconnected.messages) == 2
        with ghostty.Terminal() as restored:
            restored.feed(reconnected.messages[1][1])
            assert restored.contents() == "done"
    finally:
        output.close()


@pytest.mark.anyio
async def test_json_snapshot_between_utf8_reads():
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
        with ghostty.Terminal() as restored:
            for _, text in websocket.messages[1:]:
                restored.feed(text)
            assert restored.contents() == "before日after"
    finally:
        output.close()
