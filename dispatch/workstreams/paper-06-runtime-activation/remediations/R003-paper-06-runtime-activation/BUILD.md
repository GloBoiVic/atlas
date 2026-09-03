# R003 — Runtime contract hardening and static gate cleanup

- **Remediation ID:** `R003-paper-06-runtime-activation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin finding and source artifact:** `VALIDATION.md` `IMPORTANT-01`, `MINOR-01`, and `MINOR-02`
- **Finding severity:** `IMPORTANT` with related `MINOR` findings
- **Related original task(s):** T001, T004, T008
- **Approved requirement or invariant violated:** ARCHITECTURE §§3.1, 4.1, 4.2, 8.2, and 12.1–12.2 — all persisted runtime JSON must remain bounded and secret-free through arbitrary supported object/list nesting; opening/protection cycle statuses must bind an execution attempt identity; changed-slice formatting/lint gates must be clean.
- **Exact remediation outcome:** Recursively reject forbidden secret-bearing keys through every bounded nested list/object value; enforce that `ENTRY_CLAIMED`, `ENTRY_RESOLVED`, and `TAKE_PROFIT_CLAIMED` cycles carry an attempt ID while non-opening statuses do not; format and lint the affected runtime repository slice. Add regression coverage using sentinel values only and preserve existing persistence semantics.
- **Affected implementation seams:** `backend/runtime/persistence_contracts.py`, `backend/persistence/runtime_repository.py`, and focused runtime persistence/cycle tests.
- **Explicit out-of-scope items:** No lifecycle/orchestration/entrypoint redesign, broker mutation, retries, repair behavior, schema/migration changes, API/frontend work, Risk-policy changes, credentials, activation, LIVE/PAPER operation, or real OANDA mutation.
- **Regression evidence required:** Nested list/object secret-key rejection; valid nested JSON remains accepted; cycle attempt identity validation for opening/protection statuses and rejection for non-opening statuses; focused runtime/persistence tests, changed-slice Ruff format/check and Pyright, and `git diff --check` pass.

## Worker Evidence

- **Status:** `DONE`
- Hardened runtime JSON validation to recurse through every bounded nested
  object/list value, rejecting forbidden secret-bearing keys without retaining
  sentinel values.
- Hardened cycle attempt identity for `ENTRY_CLAIMED`, `ENTRY_RESOLVED`, and
  `TAKE_PROFIT_CLAIMED`, while retaining attempt-free non-opening statuses and
  existing completed/recovery execution identity semantics.
- Added sentinel-only nested JSON and cycle-status regression coverage.
- Formatted and lint-cleaned the changed runtime repository slice.
- **Files changed:**
  - `backend/runtime/persistence_contracts.py`
  - `backend/persistence/runtime_repository.py`
  - `backend/tests/runtime/test_runtime_persistence.py`
- **Checks:**
  - Focused runtime persistence/cycle tests: `20 passed`.
  - Full focused runtime test directory: `63 passed`.
  - Changed-slice Ruff format/check: passed.
  - Changed-slice Pyright: `0 errors, 0 warnings, 0 informations`.
  - `git diff --check`: passed.
- **Capital safety:** No credentials, activation, PAPER/LIVE operation, or
  real OANDA mutation was used.
