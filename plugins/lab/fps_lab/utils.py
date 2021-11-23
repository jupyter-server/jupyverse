import json
from glob import glob
from pathlib import Path

from typing import List, Tuple


def get_federated_extensions(extensions_dir: Path) -> Tuple[List, List]:
    federated_extensions = []
    disabledExtensions = []

    for path in glob(str(extensions_dir / "**" / "package.json"), recursive=True):
        with open(path) as f:
            package = json.load(f)
        name = package["name"]
        extension = package["jupyterlab"]["_build"]
        extension["name"] = name
        federated_extensions.append(extension)

        for ext in package["jupyterlab"].get("disabledExtensions", []):
            disabledExtensions.append(ext)

    return federated_extensions, disabledExtensions
