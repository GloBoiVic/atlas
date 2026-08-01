# Dependency Task 2 — Local Backend Environment

Use only dependencies already declared in `pyproject.toml`. Create the ignored local
`.venv` with `python -m venv .venv`, then install exactly the existing dev extra with
`.venv/bin/pip install -e ".[dev]"`. Do not edit any manifest or add packages.

Run backend checks from `.venv`:
- `.venv/bin/python -m pytest`
- `.venv/bin/python -m ruff check .`
- `.venv/bin/python -m mypy backend`

Write `.dispatch/deps-task-2-report.md`. The venv is ignored and must not be committed;
commit only the report if needed. Return status, checks, installed project/dev package
verification, and concerns.
