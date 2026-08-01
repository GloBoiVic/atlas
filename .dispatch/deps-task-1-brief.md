# Dependency Task 1 — Lockfiles

Generate lockfiles only. Do not modify `pyproject.toml`, `frontend/package.json`, or any
other manifest. Do not add any dependency.

1. Run `uv lock` in the repository root. If `uv` is not on PATH, use its existing absolute
   executable path. `uv` is a lock-generation tool only, not a project dependency.
2. Run `npm install` in `frontend/` to generate `frontend/package-lock.json`. If npm 12
   fails because of its optional-package remote restriction, use the previously validated
   fallback `npx npm@10.9.2 install --package-lock-only --ignore-scripts`.

Write a report to `.dispatch/deps-task-1-report.md`, inspect the lockfiles for manifest
changes or unapproved packages, run lockfile consistency checks where available, commit
only the lockfiles/report, and return status, commit, tests/checks, and concerns.
