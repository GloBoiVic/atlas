# R005 — Non-MT4 startup capability proof

- **Remediation ID:** `R005-paper-06-runtime-activation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin finding and source artifact:** Original `REVIEW.md` `IMPORTANT-02`
- **Finding severity:** `IMPORTANT` / `PRODUCT BLOCKER`
- **Related original task(s):** T002, T006, T008
- **Approved requirement or invariant violated:** PLAN acceptance items 1, 6, 17 and ARCHITECTURE §§1, 2, 3.1, 8.1, 12.1 — OANDA Practice, the configured USD account, and non-MT4 capability must be proven through the existing provider-specific AccountProperties path before an activation reaches `RUNNING`.
- **Exact remediation outcome:** Add a bounded read-only startup capability gate using `OandaPracticeAccountPropertiesReader` and its existing normalization semantics. The exact configured non-MT4 account may continue startup; MT4-associated, missing, mismatched, invalid, or unavailable AccountProperties must fail closed with an inspectable bounded reason under approved provider-unavailability semantics. Keep provider interpretation out of the runtime layer and add deterministic fake/transport regression coverage.
- **Affected implementation seams:** `backend/runtime/main.py`, `backend/runtime/orchestration.py`, `backend/integrations/oanda/execution_account.py` only if the existing reader seam requires adaptation, production composition, and focused runtime/OANDA tests.
- **Explicit out-of-scope items:** No generalized broker-capability abstraction, no TradeLocker or multi-broker support, no mutation/retry/repair behavior, no Risk-policy/schema/API redesign, no credentials, no activation, no LIVE/PAPER operation, and no real OANDA request or mutation.
- **Regression evidence required:** Non-MT4 exact configured account succeeds; MT4-associated account, missing/mismatched/invalid AccountProperties, and temporary read failure cannot reach `RUNNING` and expose bounded reasons; startup remains read-only and adds no direct runtime-to-OANDA mutation authority. Focused tests, changed-slice Ruff/Pyright, and `git diff --check`.

## Worker Evidence

- **Status:** `DONE`
- Added a narrow `PaperRuntimeCapabilityReader` startup seam. Runtime startup
  requires a successful read while the activation is `STARTING`, before the
  existing full Account Details/bootstrap checks can transition it to
  `RUNNING`. Runtime does not inspect provider fields or duplicate OANDA
  interpretation.
- Production composition creates one `OandaPracticeAccountPropertiesReader`
  and shares it with both startup capability proof and PAPER 05 preparation.
  The reader remains read-only and owns exact configured-account,
  non-MT4, and normalization semantics.
- MT4-associated, missing, mismatched, and malformed AccountProperties block
  with bounded `STARTUP_CAPABILITY_INVALID`. Temporary bounded provider
  failures remain `STARTING` with `WAITING_PROVIDER` and bounded
  `STARTUP_READ_UNAVAILABLE`; no activation reaches `RUNNING` or reads the
  Account Details seam until proof succeeds.
- Added deterministic startup regression coverage using fake runtime seams and
  `httpx.MockTransport`: exact non-MT4 success, all required invalid facts,
  bounded 503 retry failure, idle-without-activation, read ordering, and shared
  reader composition.
- **Files changed:**
  - `backend/runtime/orchestration.py`
  - `backend/runtime/main.py`
  - `backend/runtime/__init__.py`
  - `backend/tests/runtime/test_runtime_orchestration.py`
  - `backend/tests/test_runtime.py`
  - `dispatch/workstreams/paper-06-runtime-activation/remediations/R005-paper-06-runtime-activation/BUILD.md`
- **Checks:**
  - Focused runtime/OANDA tests: `145 passed`.
  - Changed-slice Ruff format/check: passed.
  - Changed-slice Pyright: `0 errors, 0 warnings, 0 informations`.
  - `git diff --check`: passed, including no-index checks for untracked
    implementation/test files.
- **Concerns:** No PostgreSQL integration or credentialed/external OANDA check
  was needed; R005 changes no schema and used no real credentials, activation,
  PAPER/LIVE operation, real OANDA request, or broker mutation.
