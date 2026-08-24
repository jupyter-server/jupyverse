import json

import pytest
from anyio import create_task_group, fail_after, sleep
from fps_kernel_subprocess.kernel_subprocess import KernelSubprocess

pytestmark = pytest.mark.anyio


async def test_kernelspec_env_is_passed_to_kernel(tmp_path, monkeypatch):
    # The kernel writes its env vars to a file so we can assert they reached the
    # process and that references were expanded. POSIX path: backslashes from a
    # Windows path would break the embedded string literal.
    out = tmp_path / "env_seen.txt"
    script = (
        "import os; "
        f"open('{out.as_posix()}', 'w').write("
        "os.environ.get('FPS_ENV_TEST', 'MISSING') + '|' + "
        "os.environ.get('FPS_ENV_EXPANDED', 'MISSING'))"
    )
    kernelspec = tmp_path / "kernel.json"
    kernelspec.write_text(
        json.dumps(
            {
                "argv": ["python", "-c", script, "{connection_file}"],
                "display_name": "env-test",
                "language": "python",
                "env": {
                    "FPS_ENV_TEST": "from-kernelspec",
                    "FPS_ENV_EXPANDED": "prefix:${FPS_ENV_BASE}",
                },
            }
        )
    )
    # FPS_ENV_TEST must come from the kernelspec, not be inherited from the parent.
    monkeypatch.delenv("FPS_ENV_TEST", raising=False)
    # FPS_ENV_BASE is referenced by the kernelspec `env` and must be expanded.
    monkeypatch.setenv("FPS_ENV_BASE", "base-value")

    async with create_task_group() as tg:
        kernel = KernelSubprocess(
            write_connection_file=True,
            kernelspec_path=str(kernelspec),
            connection_file="",
            kernel_cwd=str(tmp_path),
            capture_output=False,
        )
        await tg.start(kernel.start)
        try:
            with fail_after(10):
                while not out.exists():
                    await sleep(0.1)
        finally:
            await kernel.stop()

    assert out.read_text() == "from-kernelspec|prefix:base-value"
