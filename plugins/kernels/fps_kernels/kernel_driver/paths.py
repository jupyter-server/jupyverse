import os
import sys
import tempfile
from pathlib import Path
from typing import Dict, Tuple

# import glob
# import uuid


def _expand_path(s):
    # if os.name == "nt":
    #     i = str(uuid.uuid4())
    #     s = s.replace("$\\", i)
    # s = os.path.expandvars(os.path.expanduser(s))
    # if os.name == "nt":
    #     s = s.replace(i, "$\\")
    return Path(os.path.expandvars(s))


def _filefind(filename: str, path_dirs: Tuple[Path, ...] = ()) -> Path:
    filename = filename.strip('"').strip("'")
    if os.path.isabs(filename) and os.path.isfile(filename):
        return Path(filename)

    path_dirs = path_dirs or (Path(),)

    for path in path_dirs:
        # if path == ".":
        #     path = os.getcwd()
        testname = _expand_path((path / filename))
        if testname.is_file():
            return testname

    raise IOError(
        "File {} does not exist in any of the search paths: {}".format(
            filename, "\n  ".join(map(str, path_dirs))
        )
    )


_dtemps: Dict = {}


def _mkdtemp_once(name):
    if name in _dtemps:
        return _dtemps[name]
    d = _dtemps[name] = tempfile.mkdtemp(prefix=name + "-")
    return d


def jupyter_config_dir() -> Path:
    if os.environ.get("JUPYTER_NO_CONFIG"):
        return Path(_mkdtemp_once("jupyter-clean-cfg"))
    if "JUPYTER_CONFIG_DIR" in os.environ:
        return Path(os.environ["JUPYTER_CONFIG_DIR"])
    return Path.home() / ".jupyter"


def jupyter_data_dir() -> Path:
    if "JUPYTER_DATA_DIR" in os.environ:
        return Path(os.environ["JUPYTER_DATA_DIR"])

    if sys.platform == "darwin":
        return Path.home() / "Library" / "Jupyter"
    elif os.name == "nt":
        appdata = os.environ.get("APPDATA", None)
        if appdata:
            return Path(appdata) / "jupyter"
        else:
            return jupyter_config_dir() / "data"
    else:
        xdg = Path(os.environ.get("XDG_DATA_HOME", "~/.local/share"))
        return xdg / "jupyter"


def jupyter_runtime_dir():
    if "JUPYTER_RUNTIME_DIR" in os.environ:
        return Path(os.environ["JUPYTER_RUNTIME_DIR"])
    return jupyter_data_dir() / "runtime"


def find_connection_file(
    filename: str = "kernel-*.json",
    paths: Tuple[Path, ...] = (),
) -> Path:
    if not paths:
        paths = (Path(), jupyter_runtime_dir())

    path = _filefind(filename, paths)
    if path:
        return path

    if "*" in filename:
        pat = filename
    else:
        pat = f"*{filename}*"

    matches = []
    for p in paths:
        matches.extend(list(p.glob(pat)))

    # matches = [os.path.abspath(m) for m in matches]
    if not matches:
        raise IOError(f"Could not find {filename} in {paths}")
    elif len(matches) == 1:
        return matches[0]
    else:
        return sorted(matches, key=lambda p: p.stat().st_atime)[-1]
