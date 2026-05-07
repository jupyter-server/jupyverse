import subprocess
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fps_jupyterlab_git.routes import GitRouter
from httpx import ASGITransport, AsyncClient
from jupyverse_api import App


@pytest.fixture
async def git_client():
    """Fixture providing an async HTTP client and a mocked Git instance."""
    fastapi_app = FastAPI()
    app = App(fastapi_app)
    contents = AsyncMock()
    mock_git = AsyncMock()

    with patch("fps_jupyterlab_git.routes.Git") as MockGit:
        MockGit.return_value = mock_git
        GitRouter(app, contents)  # type: ignore[arg-type]

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        yield {"client": client, "git": mock_git}


@pytest.fixture
async def git_repo_client(tmp_path, monkeypatch):
    """Fixture with a real git repo — no Git mock, exercises the whole stack."""
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True)
    subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=tmp_path, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=tmp_path, check=True)

    fastapi_app = FastAPI()
    app = App(fastapi_app)
    contents = AsyncMock()
    GitRouter(app, contents)  # type: ignore[arg-type]

    async with AsyncClient(
        transport=ASGITransport(app=fastapi_app), base_url="http://test"
    ) as client:
        yield {"client": client, "path": tmp_path}
