import copy
import json
from functools import partial
from typing import Any, Callable, Dict, Optional
from uuid import uuid4

from pycrdt import Array, Doc, Map, Text

from .utils import cast_all
from .ybasedoc import YBaseDoc

# The default major version of the notebook format.
NBFORMAT_MAJOR_VERSION = 4
# The default minor version of the notebook format.
NBFORMAT_MINOR_VERSION = 5


class YNotebook(YBaseDoc):
    def __init__(self, ydoc: Optional[Doc] = None):
        super().__init__(ydoc)
        self._ymeta = Map()
        self._ycells = Array()
        self._ydoc["meta"] = self._ymeta
        self._ydoc["cells"] = self._ycells

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def ycells(self):
        return self._ycells

    @property
    def cell_number(self) -> int:
        return len(self._ycells)

    def get_cell(self, index: int) -> Dict[str, Any]:
        meta = json.loads(str(self._ymeta))
        cell = json.loads(str(self._ycells[index]))
        cell.pop("execution_status", None)
        cast_all(cell, float, int)  # cells coming from Yjs have e.g. execution_count as float
        if "id" in cell and meta["nbformat"] == 4 and meta["nbformat_minor"] <= 4:
            # strip cell IDs if we have notebook format 4.0-4.4
            del cell["id"]
        if (
            "attachments" in cell
            and cell["cell_type"] in ("raw", "markdown")
            and not cell["attachments"]
        ):
            del cell["attachments"]
        return cell

    def append_cell(self, value: Dict[str, Any]) -> None:
        ycell = self.create_ycell(value)
        self._ycells.append(ycell)

    def set_cell(self, index: int, value: Dict[str, Any]) -> None:
        ycell = self.create_ycell(value)
        self.set_ycell(index, ycell)

    def create_ycell(self, value: Dict[str, Any]) -> Map:
        cell = copy.deepcopy(value)
        if "id" not in cell:
            cell["id"] = str(uuid4())
        cell_type = cell["cell_type"]
        cell_source = cell["source"]
        cell_source = "".join(cell_source) if isinstance(cell_source, list) else cell_source
        cell["source"] = Text(cell_source)
        cell["metadata"] = Map(cell.get("metadata", {}))

        if cell_type in ("raw", "markdown"):
            if "attachments" in cell and not cell["attachments"]:
                del cell["attachments"]
        elif cell_type == "code":
            cell["outputs"] = Array(cell.get("outputs", []))
            cell["execution_status"] = "idle"

        return Map(cell)

    def set_ycell(self, index: int, ycell: Map) -> None:
        self._ycells[index] = ycell

    def get(self) -> Dict:
        meta = json.loads(str(self._ymeta))
        cast_all(meta, float, int)  # notebook coming from Yjs has e.g. nbformat as float
        cells = []
        for i in range(len(self._ycells)):
            cell = self.get_cell(i)
            if "id" in cell and meta["nbformat"] == 4 and meta["nbformat_minor"] <= 4:
                # strip cell IDs if we have notebook format 4.0-4.4
                del cell["id"]
            if (
                "attachments" in cell
                and cell["cell_type"] in ["raw", "markdown"]
                and not cell["attachments"]
            ):
                del cell["attachments"]
            cells.append(cell)

        return dict(
            cells=cells,
            metadata=meta.get("metadata", {}),
            nbformat=int(meta.get("nbformat", 0)),
            nbformat_minor=int(meta.get("nbformat_minor", 0)),
        )

    def set(self, value: Dict) -> None:
        nb_without_cells = {key: value[key] for key in value.keys() if key != "cells"}
        nb = copy.deepcopy(nb_without_cells)
        cast_all(nb, int, float)  # Yjs expects numbers to be floating numbers
        cells = value["cells"] or [
            {
                "cell_type": "code",
                "execution_count": None,
                # auto-created empty code cell without outputs ought be trusted
                "metadata": {"trusted": True},
                "outputs": [],
                "source": "",
                "id": str(uuid4()),
            }
        ]

        with self._ydoc.transaction():
            # clear document
            self._ymeta.clear()
            self._ycells.clear()
            for key in [k for k in self._ystate.keys() if k not in ("dirty", "path", "file_id")]:
                del self._ystate[key]

            # initialize document
            self._ycells.extend([self.create_ycell(cell) for cell in cells])
            self._ymeta["nbformat"] = nb.get("nbformat", NBFORMAT_MAJOR_VERSION)
            self._ymeta["nbformat_minor"] = nb.get("nbformat_minor", NBFORMAT_MINOR_VERSION)

            metadata = nb.get("metadata", {})
            metadata.setdefault("language_info", {"name": ""})
            metadata.setdefault("kernelspec", {"name": "", "display_name": ""})

            self._ymeta["metadata"] = Map(metadata)

    def observe(self, callback: Callable[[str, Any], None]) -> None:
        self.unobserve()
        self._subscriptions[self._ystate] = self._ystate.observe(partial(callback, "state"))
        self._subscriptions[self._ymeta] = self._ymeta.observe_deep(partial(callback, "meta"))
        self._subscriptions[self._ycells] = self._ycells.observe_deep(partial(callback, "cells"))
