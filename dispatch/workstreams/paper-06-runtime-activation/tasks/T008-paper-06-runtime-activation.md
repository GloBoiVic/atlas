# T008 — Restart, STOP, concurrency, and completion validation

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T006, T007
- **Owned artifact:** this file

## Objective

Close the approved PAPER 06 behavior with cross-seam deterministic and dedicated PostgreSQL integration coverage, including migration and concurrency evidence.

## Required boundaries

- Exercise every required matrix in ARCHITECTURE §12, including owner loss at each capital boundary, STOP/ENTRY linearization, restart after claims/Fill/TP claim, and unsafe states.
- Use deterministic fakes and `httpx.MockTransport`; no real OANDA mutation, activation, credentialed operation, or LIVE.
- Add only tests/fixtures/harness adjustments needed to prove the already-approved implementation; do not expand scope.

## Evidence required

- Focused runtime/PAPER regressions, dedicated PostgreSQL migration/concurrency suite, static checks for the changed slice, and `git diff --check`.

## Completed implementation

- Added deterministic cross-seam coverage in `backend/tests/runtime/test_runtime_completion_cross_seam.py` using `httpx.MockTransport` and in-memory/fake readers.
- Covered STOP/ENTRY linearization, owner loss before POST and after Fill, restart after ENTRY/POST/TP/protection claims, LONG/SHORT read-only Strategy advancement, process-loss replay, and unsupported-action fail-closed behavior.
- Added dedicated PostgreSQL completion coverage in `backend/tests/integration/test_runtime_completion.py` for runtime constraints and immutability, activation/cycle concurrency, owner-generation fencing, atomic rollback/commit, and STOP races.
- Added migration-cycle evidence in `backend/tests/integration/test_runtime_migration.py`.

## Validation evidence

- `uv run pytest -m "not integration and not external" -q`: **1037 passed, 4 skipped**.
- `ATLAS_TEST_DATABASE_URL=postgresql+psycopg://vike@localhost:5432/atlas_freeze07_test uv run pytest -m integration -q`: **111 passed, 1042 deselected**.
- Focused completion tests: **12 passed** deterministic; **8 passed** PostgreSQL completion/migration tests.
- `uv run ruff check` and `uv run ruff format --check` for all T008 test files: **passed**.
- `uv run pyright` for all T008 test files: **0 errors**.
- Dedicated database `alembic current`: `0023_paper_runtime_activation (head)`; `alembic check`: **passed**.
- `git diff --check`: **passed**.

## Concerns

- Repository-wide `ruff check backend` and `pyright backend` remain outside the T008 changed-slice gate: they report pre-existing violations in unrelated workstream files/tests. No unrelated files were edited to mask those findings.
- Integration output retains four existing `PytestUnknownMarkWarning` warnings for `price_analysis` and one existing Starlette/httpx deprecation warning.
