from __future__ import annotations

import json
import time
from typing import Any

from .yutils import Decoder, read_message


class Awareness:
    def __init__(self, ydoc):
        self.client_id = ydoc.client_id
        self.meta = {}
        self.states = {}

    def get_changes(self, message: bytes) -> dict[str, Any]:
        message = read_message(message)
        decoder = Decoder(message)
        timestamp = int(time.time() * 1000)
        added = []
        updated = []
        filtered_updated = []
        removed = []
        states = []
        length = decoder.read_var_uint()
        for _ in range(length):
            client_id = decoder.read_var_uint()
            clock = decoder.read_var_uint()
            state_str = decoder.read_var_string()
            state = None if not state_str else json.loads(state_str)
            if state is not None:
                states.append(state)
            client_meta = self.meta.get(client_id)
            prev_state = self.states.get(client_id)
            curr_clock = 0 if client_meta is None else client_meta["clock"]
            if curr_clock < clock or (
                curr_clock == clock and state is None and client_id in self.states
            ):
                if state is None:
                    if client_id == self.client_id and self.states.get(client_id) is not None:
                        clock += 1
                    else:
                        if client_id in self.states:
                            del self.states[client_id]
                else:
                    self.states[client_id] = state
                self.meta[client_id] = {
                    "clock": clock,
                    "last_updated": timestamp,
                }
                if client_meta is None and state is not None:
                    added.append(client_id)
                elif client_meta is not None and state is None:
                    removed.append(client_id)
                elif state is not None:
                    if state != prev_state:
                        filtered_updated.append(client_id)
                    updated.append(client_id)
        return {
            "added": added,
            "updated": updated,
            "filtered_updated": filtered_updated,
            "removed": removed,
            "states": states,
        }
