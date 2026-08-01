# Dependency Task 2 Report

## Status

Complete. The local `.venv` was created and installed from the existing
`pyproject.toml` using the declared `dev` extra. No manifests or package
declarations were changed.

The host does not provide a `python` executable, so the requested creation
command was executed equivalently as `python3 -m venv .venv` with Python 3.13.3.
The required install command was run unchanged:

```text
.venv/bin/pip install -e ".[dev]"
```

## Checks

| Check | Result |
| --- | --- |
| `.venv/bin/python -m pytest` | PASS: 150 passed in 8.64s |
| `.venv/bin/python -m ruff check .` | PASS: All checks passed |
| `.venv/bin/python -m mypy backend` | PASS: Success, no issues found in 35 source files |
| `.venv/bin/pip check` | PASS: No broken requirements found |

## Direct Package Verification

All direct runtime and development requirements declared in `pyproject.toml`
are installed in `.venv` and satisfy their declared version ranges.

Runtime packages:

| Declared package | Installed |
| --- | --- |
| fastapi | 0.141.1 |
| uvicorn[standard] | 0.52.0 |
| sqlalchemy[asyncio] | 2.0.51 |
| asyncpg | 0.31.0 |
| psycopg2-binary | 2.9.12 |
| alembic | 1.18.5 |
| pydantic-settings | 2.14.2 |
| python-dotenv | 1.2.2 |
| structlog | 26.1.0 |
| ccxt | 4.5.70 |
| pandas | 3.0.5 |
| numpy | 2.5.1 |
| httpx | 0.28.1 |
| websockets | 17.0.1 |
| pydantic | 2.13.4 |
| pyyaml | 6.0.3 |

Development packages:

| Declared package | Installed |
| --- | --- |
| pytest | 8.4.2 |
| pytest-asyncio | 0.26.0 |
| pytest-cov | 7.1.0 |
| aiosqlite | 0.22.1 |
| ruff | 0.16.1 |
| mypy | 1.20.2 |

The editable project itself is installed as `atlas==0.1.0`.

## Concerns

- The required bare `python -m venv .venv` command is not runnable on this
  host because `python` is absent from `PATH`; `python3` was used instead.
- The first install attempt exceeded the command timeout during its final
  transaction. The same allowed install command was rerun to completion.
- `.venv` is ignored and is not intended for commit. The report is the only
  file added by this task.
