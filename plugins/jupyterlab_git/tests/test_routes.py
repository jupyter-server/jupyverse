import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException
from fps_jupyterlab_git.routes import ContentsManagerAdapter, check_excluded_path

# ---------------------------------------------------------------------------
# Unit tests: check_excluded_path
# ---------------------------------------------------------------------------


def test_check_excluded_path_allowed():
    assert check_excluded_path("some/valid/path") == "some/valid/path"


def test_check_excluded_path_empty():
    assert check_excluded_path("") == ""


def test_check_excluded_path_git_raises():
    with pytest.raises(HTTPException) as exc_info:
        check_excluded_path(".git")
    assert exc_info.value.status_code == 404


def test_check_excluded_path_ipynb_checkpoints_raises():
    with pytest.raises(HTTPException) as exc_info:
        check_excluded_path("dir/.ipynb_checkpoints")
    assert exc_info.value.status_code == 404


# ---------------------------------------------------------------------------
# Unit tests: ContentsManagerAdapter
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_contents_manager_adapter_get():
    contents = AsyncMock()
    model = MagicMock()
    model.content = "hello"
    model.type = "file"
    model.name = "foo.py"
    contents.get_content.return_value = model
    adapter = ContentsManagerAdapter(contents)
    result = await adapter.get("foo.py")

    assert result == {"content": "hello", "type": "file", "name": "foo.py"}
    contents.get_content.assert_called_once_with("foo.py", 1, user=None)


# ---------------------------------------------------------------------------
# Handler tests (HTTP via mocked Git)
# ---------------------------------------------------------------------------


@pytest.mark.anyio
@pytest.mark.parametrize(
    "url, expected_path",
    [
        ("/git/init", "."),
        ("/git/myproject/init", "myproject"),
    ],
)
async def test_git_init_success(git_client, url, expected_path):
    client = git_client["client"]
    mock_git = git_client["git"]

    mock_git.init.return_value = {"code": 0, "message": "Initialized"}
    mock_git._empty_commit.return_value = {"code": 0, "message": ""}

    response = await client.post(url)

    assert response.status_code == 200
    mock_git.init.assert_called_once_with(expected_path)


@pytest.mark.anyio
async def test_git_init_failure(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.init.return_value = {"code": 1, "message": "error"}
    response = await client.post("/git/init")

    assert response.status_code == 500


@pytest.mark.anyio
async def test_git_init_excluded_path(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/.git/init")

    assert response.status_code == 404
    mock_git.init.assert_not_called()


# ---------------------------------------------------------------------------
# Clone
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_clone_missing_clone_url(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/clone", content=json.dumps({}))

    assert response.status_code == 400
    assert "clone_url" in response.json()["message"]
    mock_git.clone.assert_not_called()


@pytest.mark.anyio
async def test_git_clone_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.clone.return_value = {"code": 0}
    response = await client.post(
        "/git/clone",
        content=json.dumps({"clone_url": "https://example.com/repo.git"}),
    )

    assert response.status_code == 200
    mock_git.clone.assert_called_once_with(".", "https://example.com/repo.git", None, True, False)


@pytest.mark.anyio
async def test_git_clone_failure(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.clone.return_value = {"code": 1, "message": "auth failed"}
    response = await client.post(
        "/git/clone",
        content=json.dumps({"clone_url": "https://example.com/repo.git"}),
    )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_status_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.status.return_value = {"code": 0, "files": []}
    response = await client.post("/git/status")

    assert response.status_code == 200
    data = response.json()
    mock_git = git_client["git"]
    assert "files" in data
    assert data["files"] == []
    mock_git.status.assert_called_once_with(".")


@pytest.mark.anyio
async def test_git_status_failure(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.status.return_value = {"code": 128, "message": "not a git repo"}
    response = await client.post("/git/status")

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_add_missing_add_all_key(git_client):
    client = git_client["client"]
    response = await client.post("/git/add", content=json.dumps({}))

    assert response.status_code == 400
    assert "add_all" in response.json()["message"]


@pytest.mark.anyio
async def test_git_add_all_true(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.add_all.return_value = {"code": 0}
    response = await client.post("/git/add", content=json.dumps({"add_all": True}))

    assert response.status_code == 200
    mock_git.add_all.assert_called_once_with(".")
    mock_git.add.assert_not_called()


@pytest.mark.anyio
async def test_git_add_all_false_missing_filename(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/add", content=json.dumps({"add_all": False}))

    assert response.status_code == 400
    assert "filename" in response.json()["message"]
    mock_git.add.assert_not_called()


@pytest.mark.anyio
async def test_git_add_file_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.add.return_value = {"code": 0}
    response = await client.post(
        "/git/add", content=json.dumps({"add_all": False, "filename": "foo.py"})
    )

    assert response.status_code == 200
    mock_git.add.assert_called_once_with("foo.py", ".")


# ---------------------------------------------------------------------------
# Log
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_log_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.log.return_value = {"code": 0, "commits": []}
    response = await client.post("/git/log", content=json.dumps({}))

    assert response.status_code == 200
    mock_git.log.assert_called_once_with(".", 25, None)


@pytest.mark.anyio
async def test_git_log_with_options(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.log.return_value = {"code": 0, "commits": []}

    await client.post(
        "/git/log",
        content=json.dumps({"history_count": 10, "follow_path": "src/"}),
    )

    mock_git.log.assert_called_once_with(".", 10, "src/")


# ---------------------------------------------------------------------------
# Diff
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_diff_no_body(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.diff.return_value = {"code": 0, "result": ""}
    response = await client.post("/git/diff", content="{}")

    assert response.status_code == 200
    mock_git.diff.assert_called_once_with(".")


@pytest.mark.anyio
async def test_git_diff_with_refs(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.diff.return_value = {"code": 0, "result": "diff output"}
    response = await client.post(
        "/git/diff",
        content=json.dumps({"previous": "HEAD~1", "current": "HEAD"}),
    )

    assert response.status_code == 200
    mock_git.diff.assert_called_once_with(".", "HEAD~1", "HEAD")


# ---------------------------------------------------------------------------
# Branch
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_branch_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.branch.return_value = {"code": 0, "branches": []}
    response = await client.post("/git/branch")

    assert response.status_code == 200
    data = response.json()
    mock_git = git_client["git"]
    assert "branches" in data
    mock_git.branch.assert_called_once_with(".")


@pytest.mark.anyio
async def test_git_branch_delete_missing_branch(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/branch/delete", content=json.dumps({}))

    assert response.status_code == 400
    assert "branch" in response.json()["message"]
    mock_git.branch_delete.assert_not_called()


@pytest.mark.anyio
async def test_git_branch_delete_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.branch_delete.return_value = {"code": 0}
    response = await client.post(
        "/git/branch/delete", content=json.dumps({"branch": "feature/foo"})
    )

    assert response.status_code == 200
    assert response.json()["status"] == "Branch deleted successfully"
    mock_git.branch_delete.assert_called_once_with(".", "feature/foo")


@pytest.mark.anyio
async def test_git_branch_delete_failure(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.branch_delete.return_value = {"code": 1, "message": "branch not found"}
    response = await client.post(
        "/git/branch/delete", content=json.dumps({"branch": "nonexistent"})
    )

    assert response.status_code == 500


# ---------------------------------------------------------------------------
# Commit
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_commit_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.commit.return_value = {"code": 0}
    response = await client.post(
        "/git/commit", content=json.dumps({"commit_msg": "feat: add feature"})
    )

    assert response.status_code == 200
    mock_git.commit.assert_called_once_with("feat: add feature", False, ".", None)


@pytest.mark.anyio
async def test_git_commit_amend(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.commit.return_value = {"code": 0}

    await client.post(
        "/git/commit",
        content=json.dumps({"commit_msg": "fix: typo", "amend": True}),
    )

    mock_git.commit.assert_called_once_with("fix: typo", True, ".", None)


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_config_filters_allowed_options(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.config.return_value = {
        "code": 0,
        "options": {
            "user.name": "Alice",
            "user.email": "alice@example.com",
            "core.autocrlf": "true",
        },
    }
    response = await client.post(
        "/git/config",
        json={"options": {"user.name": "Alice", "core.autocrlf": "true"}},
    )

    assert response.status_code == 201
    # core.autocrlf should be filtered out from the response
    assert "core.autocrlf" not in response.json()["options"]
    assert "user.name" in response.json()["options"]
    # Only allowed options are forwarded to git
    mock_git.config.assert_called_once_with(".", **{"user.name": "Alice"})


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_settings_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.version.return_value = "2.39.0"
    response = await client.get("/git/settings")

    assert response.status_code == 200
    data = response.json()
    assert "gitVersion" in data
    assert "serverVersion" in data
    assert data["gitVersion"] == "2.39.0"


@pytest.mark.anyio
async def test_git_settings_git_not_found(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.version.side_effect = FileNotFoundError("git not found")
    response = await client.get("/git/settings")

    assert response.status_code == 500
    assert "git" in response.json()["message"].lower()


# ---------------------------------------------------------------------------
# Reset
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_reset_all(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.reset_all.return_value = {"code": 0}
    response = await client.post("/git/reset", content=json.dumps({"reset_all": True}))

    assert response.status_code == 200
    mock_git.reset_all.assert_called_once_with(".")
    mock_git.reset.assert_not_called()


@pytest.mark.anyio
async def test_git_reset_file_missing_filename(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/reset", content=json.dumps({"reset_all": False}))

    assert response.status_code == 400
    assert "filename" in response.json()["message"]
    mock_git.reset.assert_not_called()


@pytest.mark.anyio
async def test_git_reset_file_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.reset.return_value = {"code": 0}
    response = await client.post(
        "/git/reset",
        content=json.dumps({"reset_all": False, "filename": "foo.py"}),
    )

    assert response.status_code == 200
    mock_git.reset.assert_called_once_with("foo.py", ".")


# ---------------------------------------------------------------------------
# Remote add
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_remote_add_missing_url(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/remote/add", content=json.dumps({"name": "origin"}))

    assert response.status_code == 400
    assert "url" in response.json()["message"]
    mock_git.remote_add.assert_not_called()


@pytest.mark.anyio
async def test_git_remote_add_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.remote_add.return_value = {"code": 0}
    response = await client.post(
        "/git/remote/add",
        content=json.dumps({"url": "https://example.com/repo.git", "name": "origin"}),
    )

    assert response.status_code == 200
    mock_git.remote_add.assert_called_once_with(".", "https://example.com/repo.git", "origin")


# ---------------------------------------------------------------------------
# Stash
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_stash_create_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.stash.return_value = {"code": 0}
    response = await client.post("/git/stash", content=json.dumps({"stashMsg": "WIP: my changes"}))

    assert response.status_code == 200
    assert response.json()["status"] == "created"
    mock_git.stash.assert_called_once_with(".", "WIP: my changes")


@pytest.mark.anyio
async def test_git_stash_create_failure(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.stash.return_value = {"code": 1, "message": "nothing to stash"}
    response = await client.post("/git/stash", content=json.dumps({"stashMsg": ""}))

    assert response.status_code == 500


@pytest.mark.anyio
async def test_git_stash_list(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.stash_list.return_value = {"code": 0, "stashes": []}
    response = await client.get("/git/stash")

    assert response.status_code == 200
    mock_git.stash_list.assert_called_once_with(".")


@pytest.mark.anyio
async def test_git_stash_show_by_index(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.stash_show.return_value = {"code": 0, "files": []}
    response = await client.get("/git/stash", params={"index": 0})

    assert response.status_code == 200
    mock_git.stash_show.assert_called_once_with(".", 0)


@pytest.mark.anyio
async def test_git_stash_drop(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.drop_stash.return_value = {"code": 0}
    response = await client.delete("/git/stash")

    assert response.status_code == 200
    assert response.json()["status"] == "deleted"
    mock_git.drop_stash.assert_called_once_with(".")


@pytest.mark.anyio
async def test_git_stash_drop_by_index(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.drop_stash.return_value = {"code": 0}
    response = await client.delete("/git/stash", params={"stash_index": 2})

    assert response.status_code == 200
    mock_git.drop_stash.assert_called_once_with(".", 2)


# ---------------------------------------------------------------------------
# Diff notebook
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_diff_notebook_missing_keys(git_client):
    client = git_client["client"]
    response = await client.post(
        "/git/diffnotebook", content=json.dumps({"previousContent": "nb1"})
    )

    assert response.status_code == 400
    assert "Missing POST key" in response.json()["message"]


@pytest.mark.anyio
async def test_diff_notebook_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.get_nbdiff.return_value = {"base": [], "diff": []}
    response = await client.post(
        "/git/diffnotebook",
        content=json.dumps({"previousContent": "{}", "currentContent": "{}"}),
    )

    assert response.status_code == 200
    mock_git.get_nbdiff.assert_called_once_with("{}", "{}", None)


@pytest.mark.anyio
async def test_diff_notebook_error(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.get_nbdiff.side_effect = RuntimeError("nbdiff failed")
    response = await client.post(
        "/git/diffnotebook",
        content=json.dumps({"previousContent": "{}", "currentContent": "{}"}),
    )

    assert response.status_code == 500
    assert "Error diffing content" in response.json()["message"]


# ---------------------------------------------------------------------------
# Tag
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_new_tag_missing_params(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/tag", content=json.dumps({"tag_id": "v1.0"}))

    assert response.status_code == 400
    assert "required" in response.json()["message"]
    mock_git.set_tag.assert_not_called()


@pytest.mark.anyio
async def test_git_new_tag_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.set_tag.return_value = {"code": 0}
    response = await client.post(
        "/git/tag",
        content=json.dumps({"tag_id": "v1.0", "commit_id": "abc123"}),
    )

    assert response.status_code == 200
    mock_git.set_tag.assert_called_once_with(".", "v1.0", "abc123")


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_merge_missing_branch(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/merge", content=json.dumps({}))

    assert response.status_code == 400
    assert "branch" in response.json()["message"]
    mock_git.merge.assert_not_called()


@pytest.mark.anyio
async def test_git_merge_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.merge.return_value = {"code": 0}
    response = await client.post("/git/merge", content=json.dumps({"branch": "main"}))

    assert response.status_code == 200
    mock_git.merge.assert_called_once_with("main", ".")


# ---------------------------------------------------------------------------
# Delete commit / Reset to commit
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_git_delete_commit_missing_id(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    response = await client.post("/git/delete_commit", content=json.dumps({}))

    assert response.status_code == 400
    mock_git.delete_commit.assert_not_called()


@pytest.mark.anyio
async def test_git_delete_commit_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.delete_commit.return_value = {"code": 0}
    response = await client.post("/git/delete_commit", content=json.dumps({"commit_id": "abc123"}))

    assert response.status_code == 200
    mock_git.delete_commit.assert_called_once_with("abc123", ".")


@pytest.mark.anyio
async def test_git_reset_to_commit_success(git_client):
    client = git_client["client"]
    mock_git = git_client["git"]
    mock_git.reset_to_commit.return_value = {"code": 0}
    response = await client.post(
        "/git/reset_to_commit", content=json.dumps({"commit_id": "abc123"})
    )

    assert response.status_code == 200
    mock_git.reset_to_commit.assert_called_once_with("abc123", ".")


# ---------------------------------------------------------------------------
# Invalid JSON
# ---------------------------------------------------------------------------


@pytest.mark.anyio
async def test_invalid_json_body(git_client):
    client = git_client["client"]
    with pytest.raises(Exception):
        await client.post("/git/clone", content="not-json")
