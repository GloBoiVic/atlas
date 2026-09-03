# R004 — Terminal P05 outcome safety classification

- **Remediation ID:** `R004-paper-06-runtime-activation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin finding and source artifact:** Original `REVIEW.md` `IMPORTANT-01`
- **Finding severity:** `IMPORTANT` / `PRODUCT BLOCKER`
- **Related original task(s):** T004, T006, T008
- **Approved requirement or invariant violated:** PLAN acceptance items 5, 6, 14, 16 and ARCHITECTURE §§1.1–1.2, 2, 4.1, 8.3, 12.3 — durable P05 execution truth must distinguish safe definite terminal outcomes from UNKNOWN, protection-incomplete, unresolved, conflict, and malformed/incomplete truth; `FILLED_PROTECTED` is historical resolution, not current flatness.
- **Exact remediation outcome:** Correct every applicable unsafe-attempt predicate, including activation eligibility and runtime observation gating, so `NOT_RUN` alone is not unsafe for definite `REJECTED`, `CANCELLED`, or `FILLED_PROTECTED` outcomes. Keep UNKNOWN, protection-incomplete, unresolved, conflict, and missing/invalid outcomes unsafe. Preserve fresh account truth and fresh FLAT/zero-pending gates for every later new entry. Add the required truth-table and repeated-runtime regression coverage.
- **Affected implementation seams:** `backend/persistence/runtime_repository.py`, `backend/runtime/activation.py`, `backend/runtime/orchestration.py`, PAPER 05 outcome contracts/readers as directly required, and focused runtime/PAPER tests.
- **Explicit out-of-scope items:** No weakening of PAPER 05 reconciliation, no new mutation/retry/repair behavior, no broker/API redesign, no Risk-policy change, no account capability work, no schema/migration work, no credentials, no activation, no LIVE/PAPER operation, and no real OANDA request or mutation.
- **Regression evidence required:** Matrix for `REJECTED`, `CANCELLED`, `FILLED_PROTECTED`, `UNKNOWN`, `FILLED_PROTECTION_INCOMPLETE` with `NOT_RUN`; definite outcome with `UNRESOLVED` and `CONFLICT`; missing/invalid outcome. Prove normal terminal progression to fresh observation, read-only progression with known attributable open exposure and no new entry, and later fresh-flat entry gating. Changed-slice Ruff/Pyright, focused tests, and `git diff --check`.

## Worker Evidence

- **Status:** `DONE`
- Centralized the durable PAPER-attempt safety truth table in
  `is_unsafe_paper_attempt`. Definite `REJECTED`, `CANCELLED`, and
  `FILLED_PROTECTED` outcomes with `NOT_RUN` reconciliation are safe for the
  next read, while UNKNOWN, protection-incomplete, unresolved/conflicted,
  malformed, and missing truth remains unsafe. Invalid reconciliation values
  also fail closed.
- Applied the same predicate to repository observation gating, activation
  eligibility, outstanding reconciliation detection, and interrupted-cycle
  recovery. `FILLED_PROTECTED` remains historical execution resolution; fresh
  account observations still determine current flatness and exposure.
- Added the full terminal-outcome matrix and deterministic repeated-runtime
  coverage for fresh observation, attributable open exposure read-only
  progression, no-entry enforcement while non-flat, and later fresh
  FLAT/zero-pending entry/P05 gating. Tests use local fakes only; no provider
  request or mutation was made.
- **Files changed:**
  - `backend/persistence/runtime_repository.py`
  - `backend/runtime/activation.py`
  - `backend/runtime/orchestration.py`
  - `backend/tests/runtime/test_runtime_activation.py`
  - `backend/tests/runtime/test_runtime_orchestration.py`
  - `dispatch/workstreams/paper-06-runtime-activation/remediations/R004-paper-06-runtime-activation/BUILD.md`
- **Checks:**
  - Focused runtime/PAPER tests: `146 passed`.
  - Changed-slice Ruff format/check: passed.
  - Changed implementation-slice Pyright: `0 errors, 0 warnings, 0 informations`.
  - `git diff --check`: passed.
  - Relevant PostgreSQL runtime integration tests: `14 skipped`; no dedicated
    `ATLAS_TEST_DATABASE_URL` was available. R004 makes no schema/migration
    change.
- **Concerns:** The broad deterministic suite was attempted but exceeded the
  available command timeout; it was not reported as passing evidence. No
  credentials, activation, PAPER/LIVE operation, or real OANDA request or
  mutation was used.
