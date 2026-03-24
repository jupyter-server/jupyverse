import pytest
from anyio import create_task_group
from fps_kernel_subprocess.kernel_subprocess import KernelSubprocess

pytestmark = pytest.mark.anyio


@pytest.mark.parametrize("anyio_backend", ["asyncio"])
async def test_restart(tmp_path):
    p = tmp_path / "kernel.json"
    p.write_text("""{
        "argv": [
            "python",
            "-m",
            "ipykernel_launcher",
            "-f",
            "{connection_file}"
        ],
        "display_name": "Python 3 (ipykernel)",
        "language": "python",
        "metadata": {
            "debugger": true
        },
        "kernel_protocol_version": "5.5"
    }""")

    async with create_task_group() as tg:
        for i in range(100):
            kernel = KernelSubprocess(
                write_connection_file=True,
                kernelspec_path=str(p),
                connection_file="",
                kernel_cwd=str(tmp_path),
                capture_output=False,
            )

            await tg.start(kernel.start)
            await kernel.stop()
