from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fps_jupyterlab_git.routes import GitRouter
from httpx import ASGITransport, AsyncClient
from jupyverse_api import App


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.fixture
async def git_client():
    """Fixture providing an async HTTP client and a mocked Git instance."""
    fastapi_app = FastAPI()
    app = App(fastapi_app)
    contents = AsyncMock()
    mock_git = AsyncMock()

    with patch("fps_jupyterlab_git.routes.Git") as MockGit:
        MockGit.return_value = mock_git
        GitRouter(app, contents)

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        yield {"client": client, "git": mock_git}
