# Dependency Task 3 — Docker and Documentation

Do not modify any dependency manifest. Change only `Dockerfile.frontend` from `npm install`
to `npm ci`, relying on the committed `frontend/package-lock.json`.

Update `docs/codespaces.md` to document the local `.venv` workflow and locked frontend
install while preserving Docker Compose as the only API/worker/PostgreSQL validation path.
Add a TODO note to `CURRENT.md` that `Dockerfile.api` and `Dockerfile.worker` currently
install dev dependencies into runtime images; splitting dev/prod images is a separate
future concern and must not be implemented here.

Do not run Docker on the Mac host. Write `.dispatch/deps-task-3-report.md`, run text/
manifest checks and relevant non-Docker tests, commit intended files, and return status,
checks, and concerns.
