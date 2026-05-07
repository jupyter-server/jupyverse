"""Integration tests exercising the full stack: HTTP → GitRouter → real git subprocess."""

import pytest


# jupyterlab_git_core uses a module-level anyio.Lock created on first async call,
# which binds it to the first event loop backend. Force asyncio to avoid conflicts.
@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.anyio
async def test_git_status_untracked(git_repo_client):
    client = git_repo_client["client"]
    path = git_repo_client["path"]

    (path / "hello.txt").write_text("hello")

    response = await client.post("/git/status")

    assert response.status_code == 200
    data = response.json()
    assert any(f["to"] == "hello.txt" and f["x"] == "?" for f in data["files"])


@pytest.mark.anyio
async def test_git_add_stages_file(git_repo_client):
    client = git_repo_client["client"]
    path = git_repo_client["path"]

    (path / "hello.txt").write_text("hello")
    await client.post("/git/add", json={"add_all": True})

    response = await client.post("/git/status")

    assert response.status_code == 200
    data = response.json()
    assert any(f["to"] == "hello.txt" and f["x"] == "A" for f in data["files"])


@pytest.mark.anyio
async def test_git_commit_appears_in_log(git_repo_client):
    client = git_repo_client["client"]
    path = git_repo_client["path"]

    (path / "hello.txt").write_text("hello")
    await client.post("/git/add", json={"add_all": True})
    await client.post("/git/commit", json={"commit_msg": "initial commit"})

    response = await client.post("/git/log", json={})

    assert response.status_code == 200
    data = response.json()
    assert data["commits"][0]["commit_msg"] == "initial commit"


@pytest.mark.anyio
async def test_git_branch_lists_current(git_repo_client):
    client = git_repo_client["client"]
    path = git_repo_client["path"]

    (path / "hello.txt").write_text("hello")
    await client.post("/git/add", json={"add_all": True})
    await client.post("/git/commit", json={"commit_msg": "initial commit"})

    response = await client.post("/git/branch")

    assert response.status_code == 200
    data = response.json()
    current = [b for b in data["branches"] if b["is_current_branch"]]
    assert len(current) == 1


@pytest.mark.anyio
async def test_fetch_accepts_text_plain_body(git_repo_client):
    """Regression test: frontend sends Content-Type: text/plain, not application/json."""
    client = git_repo_client["client"]

    response = await client.post(
        "/git/remote/fetch",
        content="{}",
        headers={"Content-Type": "text/plain"},
    )

    # No remote configured → git error, but not a 422 body-parsing failure
    assert response.status_code != 422
