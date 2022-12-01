import os
import sys
from pathlib import Path
from typing import Dict, List

from .paths import jupyter_data_dir

if os.name == "nt":
    SYSTEM_JUPYTER_PATH = []
    programdata = os.environ.get("PROGRAMDATA", None)
    if programdata:
        SYSTEM_JUPYTER_PATH.append(Path(programdata) / "jupyter")
else:
    SYSTEM_JUPYTER_PATH = [
        Path("/usr/local/share/jupyter"),
        Path("/usr/share/jupyter"),
    ]

ENV_JUPYTER_PATH = Path(sys.prefix) / "share" / "jupyter"


def jupyter_path(*subdirs) -> List[Path]:
    paths = []
    # highest priority is env
    if os.environ.get("JUPYTER_PATH"):
        paths.append(Path(os.environ["JUPYTER_PATH"]))
    # then user dir
    paths.append(jupyter_data_dir())
    # then sys.prefix
    if ENV_JUPYTER_PATH not in SYSTEM_JUPYTER_PATH:
        paths.append(ENV_JUPYTER_PATH)
    # finally, system
    paths.extend(SYSTEM_JUPYTER_PATH)
    paths = [p for p in paths if p.is_dir()]

    # add subdir, if requested
    if subdirs:
        paths = [p.joinpath(*subdirs) for p in paths]
    return paths


def kernelspec_dirs() -> List[Path]:
    return jupyter_path("kernels")


# def _is_kernel_dir(path: Path) -> bool:
#     return path.is_dir() and (path / "kernel.json").is_file()


def _list_kernels_in(kernel_dir: Path) -> Dict[str, Path]:
    if not kernel_dir.is_dir():
        return {}
    kernels = {}
    for path in kernel_dir.glob("*/kernel.json"):
        key = path.parent.name.lower()
        kernels[key] = path.parent
    return kernels


def find_kernelspec(kernel_name: str) -> str:
    d = {}
    for kernel_dir in kernelspec_dirs():
        kernels = _list_kernels_in(kernel_dir)
        for kname, spec in kernels.items():
            if kname not in d:
                d[kname] = spec / "kernel.json"
    if kernel_name in d:
        return d[kernel_name].as_posix()
    return ""
