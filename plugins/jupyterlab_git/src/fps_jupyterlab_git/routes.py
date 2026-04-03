import fnmatch
import json

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from jupyterlab_git import __version__ as git_server_version  # type: ignore[import-untyped]
from jupyterlab_git.git import (  # type: ignore[import-untyped]
    DEFAULT_REMOTE_NAME,
    Git,
    RebaseAction,
)
from jupyverse_api import App, Router
from jupyverse_contents import Contents
from packaging.version import parse

try:
    from jupyterlab_git.ssh import SSH  # type: ignore[import-untyped]
except ImportError:
    SSH = None

ALLOWED_OPTIONS = ["user.name", "user.email"]
EXCLUDED_PATHS = [
    "*.ipynb_checkpoints",
    ".git",
]


def check_excluded_path(path: str = ""):
    if path:
        for pattern in EXCLUDED_PATHS:
            if fnmatch.fnmatchcase(path, pattern):
                raise HTTPException(status_code=404)
    return path


class ContentsManagerAdapter:
    """Adapts jupyverse Contents to the jupyter-server ContentsManager interface
    expected by jupyterlab_git (i.e. provides a .get() method and .root_dir)."""

    def __init__(self, contents: Contents):
        self.root_dir = contents.root_dir
        self._contents = contents

    async def get(self, path: str, type: str = "file") -> dict:
        model = await self._contents.get_content(path, 1, user=None)
        return {"content": model.content, "type": model.type, "name": model.name}


class GitRouter(Router):
    def __init__(self, app, contents):
        super().__init__(app)
        self.app = app
        self.git = Git()
        self.contents = contents
        router = APIRouter()

        @router.post("/git/init")
        @router.post("/git/{path:path}/init")
        async def git_init(path: str = "", checked_path: str = Depends(check_excluded_path)):
            path = checked_path or self.contents.root_dir
            result = await self.git.init(path)
            if result["code"] == 0:
                result = await self.git._empty_commit(path)

            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/clone")
        @router.post("/git/{path:path}/clone")
        async def git_clone(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            clone_url = body.get("clone_url")
            if not clone_url:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Missing 'clone_url' in request body"},
                )
            auth = body.get("auth")
            versioning = body.get("versioning", True)
            submodules = body.get("submodules", False)
            result = await self.git.clone(
                path,
                clone_url,
                auth,
                versioning,
                submodules,
            )

            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/show_top_level")
        @router.post("/git/{path:path}/show_top_level")
        async def git_show_top_level(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.show_top_level(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/remote/add")
        @router.post("/git/{path:path}/remote/add")
        async def git_remote_add(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            name = body.get("name", DEFAULT_REMOTE_NAME)
            url = body.get("url")
            if not url:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Missing 'url' in body"},
                )
            result = await self.git.remote_add(path, url, name)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.get("/git/remote")
        @router.get("/git/{path:path}/remote")
        async def git_remote_details_show(
            path: str = "", checked_path: str = Depends(check_excluded_path)
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.remote_show(path, verbose=True)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.delete("/git/remote/remove")
        @router.delete("/git/{path:path}/remote/remove")
        async def git_remote_remove(
            path: str = "",
            name: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.remote_remove(path, name)
            if result.get("code", 0) == 0:
                return JSONResponse(
                    status_code=200,
                    content={"status": "success", **result},
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=result,
                )

        @router.post("/git/add")
        @router.post("/git/{path:path}/add")
        async def git_add(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            add_all = body.get("add_all")
            if add_all is None:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Missing 'add_all' in body"},
                )
            if add_all:
                result = await self.git.add_all(path)
            else:
                filename = body.get("filename")
                if not filename:
                    return JSONResponse(
                        status_code=400,
                        content={"message": "Missing 'filename' in body"},
                    )
                result = await self.git.add(filename, path)
            return JSONResponse(
                status_code=200,
                content=result,
            )

        @router.post("/git/add_all_unstaged")
        @router.post("/git/{path:path}/add_all_unstaged")
        async def git_add_all_unstaged(
            path: str = "", checked_path: str = Depends(check_excluded_path)
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.add_all_unstaged(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/add_all_untracked")
        @router.post("/git/{path:path}/add_all_untracked")
        async def git_add_all_untracked(
            path: str = "", checked_path: str = Depends(check_excluded_path)
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.add_all_untracked(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/log")
        @router.post("/git/{path:path}/log")
        async def git_log(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            history_count = body.get("history_count", 25)
            follow_path = body.get("follow_path")
            result = await self.git.log(path, history_count, follow_path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/detailed_log")
        @router.post("/git/{path:path}/detailed_log")
        async def git_detailed_log(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            selected_hash = body.get("selected_hash")
            if not selected_hash:
                return JSONResponse(
                    status_code=500,
                    content={"message": "Missing 'selected_hash' in request body"},
                )
            result = await self.git.detailed_log(selected_hash, path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.get("/git/submodules")
        @router.get("/git/{path:path}/submodules")
        async def git_submodules(
            path: str = "", checked_path: str = Depends(check_excluded_path)
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.submodule(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.get("/git/settings")
        async def git_settings(
            version: str | None = None,
            checked_path: str = Depends(check_excluded_path),
        ):
            jlab_version = str(parse(version)) if version else None
            git_version = None
            try:
                git_version = await self.git.version()
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "message": f"[jupyterlab_git] Failed to execute 'git' command: {e}"
                    },
                )
            server_version = str(git_server_version)
            return {
                "frontendVersion": jlab_version,
                "gitVersion": git_version,
                "serverVersion": server_version,
            }

        @router.post("/git/config")
        @router.post("/git/{path:path}/config")
        async def git_config(
            path: str = "",
            body: dict = Body(default={}),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            options = body.get("options", {})
            filtered_options = {k: v for k, v in options.items() if k in ALLOWED_OPTIONS}
            result = await self.git.config(path, **filtered_options)
            if "options" in result:
                result["options"] = {
                    k: v for k, v in result["options"].items() if k in ALLOWED_OPTIONS
                }
            return JSONResponse(
                status_code=201 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/branch")
        @router.post("/git/{path:path}/branch")
        async def git_branch(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.branch(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/branch/delete")
        @router.post("/git/{path:path}/branch/delete")
        async def git_branch_delete(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            branch_name = body.get("branch")
            if not branch_name:
                return JSONResponse(
                    status_code=400, content={"message": "Missing 'branch' in body"}
                )
            result = await self.git.branch_delete(path, branch_name)
            if result["code"] == 0:
                return JSONResponse(
                    status_code=200,
                    content={"status": "Branch deleted successfully", **result},
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=result,
                )

        @router.post("/git/tags")
        @router.post("/git/{path:path}/tags")
        async def tags(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.tags(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/show_prefix")
        @router.post("/git/{path:path}/show_prefix")
        async def show_prefix(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.show_prefix(path, self.contents)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/changed_files")
        @router.post("/git/{path:path}/changed_files")
        async def git_changed_files(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            result = await self.git.changed_files(path, **body)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/status")
        @router.post("/git/{path:path}/status")
        async def git_status(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.status(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/content")
        @router.post("/git/{path:path}/content")
        async def git_content(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            filename = body["filename"]
            reference = body["reference"]
            cm = ContentsManagerAdapter(self.contents)
            result = await self.git.get_content_at_reference(filename, reference, path, cm)
            return JSONResponse(
                status_code=200,
                content=result,
            )

        @router.post("/git/diff")
        @router.post("/git/{path:path}/diff")
        async def git_diff(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            if body:
                result = await self.git.diff(
                    path,
                    body.get("previous"),
                    body.get("current"),
                )
            else:
                result = await self.git.diff(path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/remote/fetch")
        @router.post("/git/{path:path}/remote/fetch")
        async def git_remote_fetch(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            auth = body.get("auth", None)
            result = await self.git.fetch(path, auth)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.get("/git/remote/show")
        @router.get("/git/{path:path}/remote/show")
        async def git_remote_show(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.remote_show(path, verbose=True)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/upstream")
        @router.post("/git/{path:path}/upstream")
        async def git_upstream(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            current_branch = await self.git.get_current_branch(path)
            result = await self.git.get_upstream_branch(path, current_branch)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.get("/git/check_notebooks")
        @router.get("/git/{path:path}/check_notebooks")
        async def check_notebooks(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = await self.git.check_notebooks_with_outputs(path)
            return JSONResponse(
                status_code=200,
                content=result,
            )

        @router.post("/git/strip_notebooks")
        @router.post("/git/{path:path}/strip_notebooks")
        async def strip_notebooks(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            notebooks = body.get("notebooks", [])
            try:
                await self.git.strip_notebook_outputs(notebooks, path)
                return JSONResponse(
                    status_code=200,
                    content={"code": 0, "message": "Notebooks stripped"},
                )
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={
                        "code": 1,
                        "message": f"Failed to strip notebook outputs: {str(e)}",
                    },
                )

        @router.post("/git/diffnotebook")
        async def diff_notebook(
            raw_body: str = Body(default="{}"),
        ):
            body = json.loads(raw_body)
            try:
                prev_content = body["previousContent"]
                curr_content = body["currentContent"]
            except KeyError as e:
                return JSONResponse(
                    status_code=400,
                    content={"message": f"Missing POST key: {e}"},
                )
            try:
                base_content = body.get("baseContent")
                content = await self.git.get_nbdiff(prev_content, curr_content, base_content)
            except Exception as e:
                return JSONResponse(
                    status_code=500,
                    content={"message": f"Error diffing content: {e}."},
                )
            return JSONResponse(
                status_code=200,
                content=content,
            )

        @router.post("/git/commit")
        @router.post("/git/{path:path}/commit")
        async def git_commit(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            commit_msg = body["commit_msg"]
            amend = body.get("amend", False)
            author = body.get("author")
            result = await self.git.commit(commit_msg, amend, path, author)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/rebase")
        @router.post("/git/{path:path}/rebase")
        async def git_rebase(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            branch = body.get("branch")
            action = body.get("action", "")
            if branch is not None:
                result = await self.git.rebase(branch, path)
            else:
                result = await self.git.resolve_rebase(
                    path,
                    RebaseAction[action.upper()],
                )
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/tag")
        @router.post("/git/{path:path}/tag")
        async def git_new_tag(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            tag = body.get("tag_id")
            commit = body.get("commit_id")
            if not tag or not commit:
                return JSONResponse(
                    status_code=400,
                    content={"message": "tag_id and commit_id are required"},
                )
            result = await self.git.set_tag(path, tag, commit)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/tag_checkout")
        @router.post("/git/{path:path}/tag_checkout")
        async def git_tag_checkout(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            tag = body.get("tag_id")
            if not tag:
                return JSONResponse(status_code=400, content={"message": "tag_id is required"})
            result = await self.git.tag_checkout(path, tag)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.get("/git/ignore")
        @router.get("/git/{path:path}/ignore")
        async def git_read_gitignore(
            path: str = "",
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            result = self.git.read_file(f"{path}/.gitignore")
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/ignore")
        @router.post("/git/{path:path}/ignore")
        async def git_update_gitignore(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            file_path = body.get("file_path")
            content = body.get("content")
            use_extension = body.get("use_extension", False)
            result = await self.git.update_gitignore(
                path,
                file_path=file_path,
                content=content,
                use_extension=use_extension,
            )
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/reset")
        @router.post("/git/{path:path}/reset")
        async def git_reset(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            if body.get("reset_all"):
                result = await self.git.reset_all(path)
            else:
                filename = body.get("filename")
                if not filename:
                    return JSONResponse(
                        status_code=400,
                        content={"message": "Missing filename for reset"},
                    )
                result = await self.git.reset(filename, path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/delete_commit")
        @router.post("/git/{path:path}/delete_commit")
        async def git_delete_commit(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            commit_id = body.get("commit_id")
            if not commit_id:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Missing commit_id"},
                )
            result = await self.git.delete_commit(commit_id, path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/reset_to_commit")
        @router.post("/git/{path:path}/reset_to_commit")
        async def git_reset_to_commit(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            commit_id = body.get("commit_id")
            if not commit_id:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Missing commit_id"},
                )
            result = await self.git.reset_to_commit(commit_id, path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/checkout")
        @router.post("/git/{path:path}/checkout")
        async def git_checkout(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            if body.get("checkout_branch"):
                result = await self.git.checkout_branch_safe(
                    body.get("branchname"),
                    body.get("startpoint"),
                    path,
                    new_branch=body.get("new_check"),
                )
            elif body.get("checkout_all"):
                result = await self.git.checkout_all(path)
            else:
                filename = body.get("filename")
                if not filename:
                    return JSONResponse(
                        status_code=400,
                        content={"message": "Missing filename for checkout"},
                    )
                result = await self.git.checkout(filename, path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/merge")
        @router.post("/git/{path:path}/merge")
        async def git_merge(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            branch = body.get("branch")
            if not branch:
                return JSONResponse(
                    status_code=400,
                    content={"message": "Missing branch for merge"},
                )
            result = await self.git.merge(branch, path)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/stash")
        @router.post("/git/{path:path}/stash")
        async def git_stash(
            path: str = "",
            raw_body: str = Body(...),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            stash_msg = body.get("stashMsg", "")
            result = await self.git.stash(path, stash_msg)
            if result["code"] == 0:
                return JSONResponse(
                    status_code=200,
                    content={"status": "created", **result},
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=result,
                )

        @router.delete("/git/stash")
        @router.delete("/git/{path:path}/stash")
        async def git_stash_drop(
            path: str = "",
            stash_index: int | None = Query(None),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            if stash_index is None:
                result = await self.git.drop_stash(path)
            else:
                result = await self.git.drop_stash(path, stash_index)
            if result["code"] == 0:
                return JSONResponse(
                    status_code=200,
                    content={"status": "deleted", **result},
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=result,
                )

        @router.get("/git/stash")
        @router.get("/git/{path:path}/stash")
        async def git_stash_list(
            path: str = "",
            index: int | None = Query(None),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            if index is None:
                result = await self.git.stash_list(path)
            else:
                result = await self.git.stash_show(path, index)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/stash_pop")
        @router.post("/git/{path:path}/stash_pop")
        async def git_stash_pop(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            index = body.get("index")
            result = await self.git.pop_stash(path, index)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/stash_apply")
        @router.post("/git/{path:path}/stash_apply")
        async def git_stash_apply(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            index = body.get("index")
            result = await self.git.apply_stash(path, index)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/pull")
        @router.post("/git/{path:path}/pull")
        async def git_pull(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            auth = body.get("auth")
            cancel_on_conflict = body.get("cancel_on_conflict")
            result = await self.git.pull(path, auth, cancel_on_conflict)
            return JSONResponse(
                status_code=200 if result["code"] == 0 else 500,
                content=result,
            )

        @router.post("/git/push")
        @router.post("/git/{path:path}/push")
        async def git_push(
            path: str = "",
            raw_body: str = Body(default="{}"),
            checked_path: str = Depends(check_excluded_path),
        ):
            path = checked_path or self.contents.root_dir
            body = json.loads(raw_body)
            known_remote = body.get("remote")
            force = body.get("force", False)
            auth = body.get("auth")
            result = await self.git.push_current_branch(
                local_path=path, remote=known_remote, auth=auth, force=force
            )
            if result["code"] == 0:
                return JSONResponse(
                    status_code=200,
                    content={"status": "applied", **result},
                )
            else:
                return JSONResponse(
                    status_code=500,
                    content=result,
                )

        if SSH is not None:

            @router.get("/git/known_hosts")
            async def ssh_known_hosts_get(
                hostname: str = Query(...),
            ):
                ssh = SSH()
                is_known_host = ssh.is_known_host(hostname)
                return JSONResponse(status_code=200, content=is_known_host)

            @router.post("/git/known_hosts")
            async def ssh_known_hosts_post(
                raw_body: str = Body(...),
            ):
                body = json.loads(raw_body)
                hostname = body["hostname"]
                ssh = SSH()
                ssh.add_host(hostname)
                return JSONResponse(status_code=200, content={})

        self.include_router(router)
