# Working in this repository

- Check `git status --short` before making changes. Preserve unrelated changes
  and untracked files, including local databases and `uv.lock`.
- This is a Python workspace: the root `jupyverse` package, API packages in
  `api/*`, and plugin packages in `plugins/*` have independent versions.
- The release repository is `jupyter-server/jupyverse`. Verify remote URLs rather
  than assuming `origin` points there; this checkout may use `upstream` for it.

## Release process

1. Inspect `.github/workflows/publish-release.yml`, the latest upstream release,
   upstream `main`, and its CI results. Confirm the intended release base matches
   upstream and review all changes since the previous release tag.
2. Select the next root package version and identify which workspace packages
   changed since the last release. Choose the bump for each package separately:
   - Patch (`x.y.Z`): backward-compatible fixes and dependency updates.
   - Minor (`x.Y.0`): backward-compatible features. For packages below 1.0, also
     use a minor bump for breaking changes and describe the migration in the
     changelog.
   - Major (`X.0.0`): breaking changes for packages at or above 1.0. Moving a
     package to 1.0 is an explicit stability decision, not an automatic bump.
   Use the highest bump required by the changes included in each package.
   Bump versions manually by editing `[project].version` in the root and affected
   packages' `pyproject.toml` files. Update dependency lower bounds in consuming
   packages where needed so they require the new behavior. Review whether any
   consumers also need a version bump. Check both `[project].dependencies` and
   `[project.optional-dependencies]`; adjust upper bounds if the new version
   falls outside the existing range. Do not bump every workspace package.
3. Update the relevant `pyproject.toml` files. Add a section at the top of
   `CHANGELOG.md`, using the plain version as its heading. Describe user-visible
   changes and list the additional packages released with their new versions,
   following the existing changelog format.
4. Verify the release:
   - Check upstream CI for the release base. The test workflow covers Linux,
     macOS, Windows, and the supported Python versions, plus typing and lint.
   - For local checks, create `.venv` if it does not already exist, then install
     the workspace packages and test dependencies from the repository root:
     ```bash
     uv venv
     uv pip install --group test -e . -e api/* -e plugins/*
     ```
     Skip environment creation when reusing an existing `.venv`. These commands
     follow CI's installation process without clearing an existing environment.
   - Require the full test suite to pass for the release base, either in
     upstream CI or locally:
     ```bash
     uv run --no-sync pytest -q --timeout=60
     ```
     If only package versions, dependency lower bounds, and release notes
     changed afterward, a local rerun is optional.
     Integration tests need local sockets and PTYs. If sandbox restrictions
     prevent these operations, rerun with the required permissions; distinguish
     environment failures from test failures.
   - Build the workspace as the publishing workflow does:
     ```bash
     uv build --all-packages --out-dir /tmp/jupyverse-release-VERSION
     ```
     Substitute the selected version in the output path. Keep build artifacts
     outside the checkout and preserve any existing untracked lockfile.
   - Run `git diff --check` and inspect the final diff. Confirm that versions,
     dependency bounds, and the changelog agree.
5. Stage only the release files and commit with `Release vVERSION`. Create a tag
   named `VERSION`, **without a `v` prefix**. Recent release tags use this format,
   and the publishing workflow matches it.
6. When publication is authorized, push the release commit and tag to
   `jupyter-server/jupyverse`. Prefer an atomic push, for example when that remote
   is named `upstream` and the release branch is `main`:
   ```bash
   git push --atomic upstream main refs/tags/VERSION
   ```
   Pushing the tag triggers package publication to PyPI and creation of the
   GitHub release. Do not push the tag until verification is complete.
7. Monitor the Publish workflow, then verify the GitHub release notes and the
   availability of every newly versioned package on PyPI. Report the release
   link and any remaining publication failures.

## Publishing workflow caveat

The workflow builds and attempts to publish **all** workspace packages. Unchanged
versions may already exist on PyPI. Its upload loop uses `uv publish ... ||
continue`, so a successful workflow alone does not prove that every new package
was uploaded. Verify the newly released versions explicitly before reporting
publication as complete.

If a release command is interrupted, inspect the local commit, tag, remote refs,
and workflow state before retrying: part of the operation may have completed.
