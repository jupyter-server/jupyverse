import pytest

from .jupyverse_adapter import JupyverseAdapter


@pytest.mark.parametrize("auth_mode", ("noauth",))
@pytest.mark.parametrize("clear_users", (False,))
def test_multiple_kernel_restarts(start_jupyverse):
    url = start_jupyverse
    jupyverse_adapter = JupyverseAdapter(url)
    for _ in range(5):
        kernel_id, session_id = jupyverse_adapter.new_session()
        jupyverse_adapter.kernel_info_request(kernel_id, session_id)
        jupyverse_adapter.stop_kernel(kernel_id)
