# T002 — Activation and control contracts

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Depends on:** T001
- **Owned artifact:** this file

## Objective

Implement explicit local activation, STOP, capability, status, and reconcile contracts plus guarded application services over T001 persistence.

## Required boundaries

- Validate exact activation request identity, immutable Strategy provenance/parameters, Risk decimal, confirmation, server-bound Practice/USD/EUR_USD configuration, and token presence without persisting or logging secrets.
- Provide same-ID exact replay and same-ID identity conflict semantics; reject a different request while a non-terminal activation occupies the slot.
- Keep process liveness unrelated to activation authority.
- Enforce local authority middleware and real request metadata for PAPER control/status routes.
- STOP and reconcile remain read-only with respect to broker mutation; reconcile delegates to existing PAPER 05 GET-only authority.
- Do not implement runtime cadence, ownership acquisition, or Strategy evaluation in this task.

## Evidence required

- Deterministic service/contract tests for schema, idempotency, conflicts, local authorization, secret redaction, STOP idempotency, and reconcile refusal/concurrency semantics.

## Completion receipt

Implemented the explicit local PAPER activation and control service boundary over
T001 persistence.  The service validates the fixed OANDA Practice/USD/EUR_USD
scope, exact Strategy provenance and parameters, finite Decimal Risk, approval,
and token/account configuration without persisting or exposing credentials.  It
maps exact activation replay/conflict behavior, single-slot contention, durable
STOP fencing/idempotency, separate runtime/broker status, and terminal-only
bounded PAPER 05 reconciliation.

### Files changed

- `backend/runtime/activation.py`
- `backend/runtime/__init__.py`
- `backend/api/schemas.py`
- `backend/persistence/runtime_repository.py`
- `backend/tests/runtime/test_runtime_activation.py`

### Checks and evidence

- Focused activation/control and existing runtime regression tests: `15 passed`.
- Dedicated PostgreSQL `atlas_t002_test` runtime repository and migration tests: `5 passed`.
- Alembic `current`: `0023_paper_runtime_activation (head)`.
- Alembic `check`: no new upgrade operations detected.
- Changed-slice Ruff format/check, Pyright (`--threads 1`), import smoke check, and `git diff --check`: passed.
- No OANDA calls, PAPER activation, credentials, or broker mutation were used.

### Concerns / handoff

- FastAPI route wiring, local-authority request metadata enforcement, and HTTP
  status projections remain T007 scope.
- The broad non-integration suite was attempted but exceeded the 120-second
  command timeout before completion; no test failure was reported in the
  portion executed.
- The existing shared `atlas_test` database references an unavailable `0026`
  migration, so integration evidence used the fresh dedicated `atlas_t002_test`
  database instead.
