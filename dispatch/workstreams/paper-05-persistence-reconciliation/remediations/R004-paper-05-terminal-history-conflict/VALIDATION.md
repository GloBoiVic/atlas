# R004 Validation — PAPER 05 Terminal-History Conflict

- **Remediation ID:** `R004`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `VALIDATE`
- **Status:** `PASS`
- **Origin:** R003 `IMPORTANT` / `PRODUCT` finding that a later attributable Fill after durable `REJECTED`/`CANCELLED` history lacks retained reconciliation conflict status

## Validation mandate

Independently validate R004 against the frozen `PLAN.md` and `ARCHITECTURE.md`,
the immutable R003 `VALIDATION.md` finding, the R004 BUILD receipt, current source,
and the R004 test diff. First reproduce the R003 failing validator probe. Then
verify the exact and bounded-range terminal-history matrix, downstream missing and
exact protected Trade behavior, NULL/UNKNOWN controls, adjacent no-Fill terminal
matrix, existing simultaneous Fill + reject/cancel range coverage, preservation of
durable Fill/terminal evidence, and the unchanged persistence transition contract.

Run the focused reconciliation/PAPER/OANDA regressions and the appropriate broad
safe backend/static gates already required by PAPER 05. Use deterministic fakes,
`httpx.MockTransport`, and dedicated test database state where available only.
No real OANDA request, credential, activation, runtime, broker mutation, or
capital-capable action is permitted. This role writes only this artifact and must
not modify application, tests, fixtures, migrations, or prior evidence.

If another Critical or Important PRODUCT defect is found, STOP: record the exact
finding and do not create R005 automatically.

## Independent validation

R004 passes the approved narrow remediation scope. The former R003 contradiction
probe no longer reproduces against the current implementation: prior durable
`REJECTED`/`CANCELLED` history followed by an attributable Fill now advances the
execution outcome to filled truth and retains `CONFLICT` status/finding.

The implementation preserves the frozen persistence transition contract. The
`REJECTED`/`CANCELLED` → filled transition remains in
`validate_execution_outcome_transition`; R004 changes only coordinator-side
historical conflict classification and its deterministic coverage.

### R004 acceptance matrix

`uv run pytest -q backend/tests/paper/test_reconciliation.py -k
'later_fill_after_terminal_history or later_fill_after_rejection_history or
terminal_history_conflict or later_fill_without_terminal_history or
same_later_terminal_history or contradictory_later_terminal_history'`

- **12 passed**, 17 deselected.
- The 12 cases cover exact and bounded-range later Fills after both prior
  `REJECTED` and `CANCELLED`; missing Trade and exact protected Trade paths;
  read-failure preservation; `NULL`/`UNKNOWN` controls; same-terminal replays;
  and contradictory no-Fill terminal replays.
- The exact/range matrix proves Fill persistence, filled-outcome advancement,
  retained prior rejection evidence, `CONFLICT` status/finding retention, and
  no conflict solely from Fill discovery with `NULL`/`UNKNOWN` history.

### Regression evidence

- `uv run pytest -q backend/tests/paper backend/tests/integrations/test_oanda_reconciliation.py`
  — **107 passed**. This includes the complete reconciliation tests and the
  deterministic GET-only OANDA reconciliation/MockTransport tests.
- `uv run pytest -q -m "not integration and not external"` — **975 passed, 4
  skipped, 97 deselected, 4 existing warnings**.
- `uv run pytest -q backend/tests/integration/test_paper_execution_repository.py`
  — **9 skipped** because `ATLAS_TEST_DATABASE_URL` was not set to a dedicated
  `*_test` database. R004 changes no persistence model, migration, or repository
  code; prior R003 PostgreSQL evidence remains the applicable persistence proof.
- Changed-slice static gates passed:
  `uv run ruff format --check backend/paper/reconciliation.py
  backend/tests/paper/test_reconciliation.py`,
  `uv run ruff check backend/paper/reconciliation.py
  backend/tests/paper/test_reconciliation.py`, and
  `uv run pyright backend/paper/reconciliation.py
  backend/tests/paper/test_reconciliation.py` (**0 errors, 0 warnings, 0
  informations**).
- `git diff --check` passed.
- Repository-wide static probes retain unrelated baseline failures:
  `ruff format --check backend` reports 68 unformatted files, `ruff check
  backend` reports 28 errors, and `pyright backend` reports 2887 errors; none
  are in the R004 changed implementation/test slice.
- `uv run alembic current` reports `0020_fix_snapshot_guard`; `uv run alembic
  check` fails because the configured database is not up to date. R004 made no
  schema or migration change and no database action was taken.
- No real OANDA request, credential, broker mutation, PAPER activation, runtime
  operation, or capital-capable action occurred.

## Findings

No Critical or Important PRODUCT defect was found within the approved R004 scope.
The repository-wide static failures, stale configured Alembic database, and
skipped PostgreSQL integration fixture are recorded concerns only; they are not
caused by R004 and do not affect the deterministic behavior validated above.

## Completion Receipt

ROLE: VALIDATE
STATUS: PASS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R004-paper-05-terminal-history-conflict/VALIDATION.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Former R003 contradiction probe and complete R004 matrix 12 passed; focused PAPER/OANDA reconciliation suite 107 passed; broad safe backend 975 passed, 4 skipped, 97 deselected; changed-slice Ruff/Pyright and `git diff --check` passed; PostgreSQL integration skipped for absent dedicated test URL; repository-wide static and Alembic baseline/environment failures documented; fake-only deterministic evidence with no broker mutation or capital-capable action.
FINDINGS / CONCERNS: PASS — no additional Critical or Important PRODUCT defect. Repository-wide Ruff/Pyright failures and stale Alembic target remain pre-existing/environmental concerns; no R005 is warranted or authorized.
