# TASK-10 — Integration test isolation (OBS-2)

Status: **DONE**

Owner: this workstream. Resolves the single Important review finding **OBS-2**
in `REVIEW.md` (`dispatch/workstreams/first-historical-trade/REVIEW.md`):
the full suite did not pass as one command because the PostgreSQL integration
tests share one `*_test` database and were not mutually isolated.

## Root cause

All integration test files run against the same shared PostgreSQL database
(`ATLAS_TEST_DATABASE_URL`, name ends in `_test`). They seed overlapping
fixtures (most concretely the `EUR/USD` instrument, hardcoded at
`test_fill_application.py:59-62` with no truncation/conflict handling) and do
not clean up after themselves in a way that protects a later invocation:

- `test_golden_flows.py` truncates the shared tables at the *start* of each
  test but leaves its rows behind when it finishes, so a subsequent
  `pytest -q` begins with `EUR/USD` already present.
- `test_fill_application.py` runs *before* `test_golden_flows.py`
  (alphabetical collection) and inserts a hardcoded `EUR/USD` instrument with
  no truncation or `ON CONFLICT` guard, so the leftover row triggers a
  `UniqueViolation … "uq_instruments_code"`.
- `test_strategy_persistence.py`'s module fixture downgrades the schema to
  `base` on teardown, and `test_fill_application.py` never runs migrations
  itself, so a prior partial invocation can also leave the schema at `base`
  (`relation does not exist`).

Each integration file passes in isolation on a clean database, but the suite is
order/state-dependent across invocations.

**Reproduced:** with `EUR/USD` residue present, a single `pytest -q` returned
`2 failed, 168 passed, 1 skipped`, both failures in `test_fill_application.py`
with `IntegrityError … UniqueViolation … Key (code)=(EUR/USD) already exists`.

## Minimal remediation (test-only)

Added one new test-infrastructure file, `backend/tests/integration/conftest.py`,
with two autouse fixtures:

1. `_ensure_integration_schema` (session scope) — runs `alembic upgrade head`
   once per integration session, so a full run is self-sufficient regardless of
   the schema state a previous invocation left (base or head).
2. `_isolate_integration_database` (function scope) — truncates every data
   table in the public schema (via `TRUNCATE ... CASCADE`) before each
   integration test, so no test observes another test's rows.

`TRUNCATE ... CASCADE` is used because it bypasses the row-level immutability
triggers (which only guard DML row transitions), so it can clear
append-only/terminal rows that a guarded DELETE cannot — the same mechanism the
existing integration files already use for their own cleanup. No application
code, production schema, migration, or test assertion was changed; no Phase 3
behavior was altered.

## Validation receipts

- Full suite as a single command, `EUR/USD` residue present (the OBS-2
  reproduction) — `python -m pytest -q` → **170 passed, 1 skipped**.
- Full suite from a **base** schema (worst-case prior-state leak) — `python -m
  pytest -q` → **170 passed, 1 skipped**.
- Consecutive full-suite runs (cross-run isolation) — `python -m pytest -q`
  twice → **170 passed, 1 skipped** each.
- Targeted integration directory — `python -m pytest -q
  backend/tests/integration/` → **18 passed**.
- Non-integration suite — `python -m pytest -q -m "not integration"` → **151
  passed, 1 skipped, 19 deselected**.
- `ruff check backend/tests/integration/conftest.py` — **passed**.
- `pyright backend/tests/integration/conftest.py` — **0 errors, 0 warnings**.

All integration runs emit only the pre-existing FastAPI/httpx deprecation
warning; no test failures.

## Scope and exclusions

- Only test infrastructure was added. `git status` shows the sole change from
  this task is the new untracked file `backend/tests/integration/conftest.py`;
  no tracked implementation or test file was modified by this task.
- The NY-calendar coupling (OBS-1) and runner pyright findings (OBS-3) were
  explicitly out of scope and were **not** touched.
- The 19th integration-marked test, `backend/tests/market_data/test_cli.py`
  (`test_cli_load_uses_fake_source_and_dedicated_database`), does not use the
  shared `*_test` database and is unaffected by this change.

## Blocker

None. The full suite passes as one command (`170 passed, 1 skipped`) from both
the residue-present (OBS-2 reproduction) and base-schema states, and remains
green across consecutive invocations.
