import json

import pytest
from anyio import create_task_group, fail_after, sleep
from fps_kernel_subprocess.kernel_subprocess import KernelSubprocess

pytestmark = pytest.mark.anyio


async def test_kernelspec_env_is_passed_to_kernel(tmp_path, monkeypatch):
    # The kernel writes an env var (declared in the kernelspec `env`) to a file,
    # so we can assert the kernelspec environment actually reached the process.
    out = tmp_path / "env_seen.txt"
    script = f"import os; open('{out}', 'w').write(os.environ.get('FPS_ENV_TEST', 'MISSING'))"
    kernelspec = tmp_path / "kernel.json"
    kernelspec.write_text(
        json.dumps(
            {
                "argv": ["python", "-c", script, "{connection_file}"],
                "display_name": "env-test",
                "language": "python",
                "env": {"FPS_ENV_TEST": "from-kernelspec"},
            }
        )
    )
    # The value must come from the kernelspec, not be inherited from the parent.
    monkeypatch.delenv("FPS_ENV_TEST", raising=False)

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

    assert out.read_text() == "from-kernelspec"
