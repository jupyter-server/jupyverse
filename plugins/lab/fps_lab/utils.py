import json
from pathlib import Path
from typing import List, Tuple


def get_federated_extensions(extensions_dir: Path) -> Tuple[List, List]:
    federated_extensions = []
    disabledExtensions = []

    for path in extensions_dir.rglob("**/package.json"):
        with open(path) as f:
            package = json.load(f)
        if "jupyterlab" not in package:
            continue
        name = package["name"]
        extension = package["jupyterlab"]["_build"]
        extension["name"] = name
        federated_extensions.append(extension)

        for ext in package["jupyterlab"].get("disabledExtensions", []):
            disabledExtensions.append(ext)

    return federated_extensions, disabledExtensions
