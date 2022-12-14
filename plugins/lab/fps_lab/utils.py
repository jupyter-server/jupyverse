import json
import os
from glob import glob
from pathlib import Path
from typing import List, Tuple


def get_federated_extensions(extensions_dir: Path) -> Tuple[List, List]:
    federated_extensions = []
    disabled_extensions = []

    for path in glob(os.path.join(extensions_dir, "**", "package.json"), recursive=True):
        with open(path) as f:
            package = json.load(f)
        if "jupyterlab" not in package:
            continue
        extension = package["jupyterlab"]["_build"]
        extension["name"] = package["name"]
        extension["description"] = package["description"]
        federated_extensions.append(extension)

        for ext in package["jupyterlab"].get("disabledExtensions", []):
            disabled_extensions.append(ext)

    return federated_extensions, disabled_extensions
