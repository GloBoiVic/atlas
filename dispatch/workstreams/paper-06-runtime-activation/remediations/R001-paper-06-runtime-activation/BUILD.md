# R001 — Owner-loss fence before dependent protection mutation

- **Remediation ID:** `R001-paper-06-runtime-activation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin finding and source artifact:** `VALIDATION.md` `CRITICAL-01 — Owner loss is not fenced between the Take Profit claim and PUT`
- **Finding severity:** `CRITICAL`
- **Related original task(s):** T006, T008
- **Approved requirement or invariant violated:** ARCHITECTURE §§4, 7.7, 9.1, 12.1 — owner loss fences post-claim network dispatch that is not already protected by a valid owner; an already-authorized same-process dependent protection operation may proceed only while the valid owner remains held.
- **Exact remediation outcome:** Add an immediately preceding valid owner/generation fence between committed Take Profit claim evidence and the dependent OANDA protection PUT. On owner loss, retain the claim and fail closed without PUT; preserve the existing same-process protection path when ownership remains valid. Add deterministic coverage for the claim-commit-to-PUT owner-loss window without real provider mutation.
- **Affected implementation seams:** `backend/paper/durable_execution.py`, `backend/runtime/orchestration.py`, the existing P05 protection callback seam, and focused runtime/PAPER tests; follow directly affected OANDA mutation callback code only if required by the existing seam.
- **Explicit out-of-scope items:** No new claims, retries, repair behavior, restart-time mutation, broker/API redesign, Risk-policy change, runtime entrypoint work, secret-validation work, credential use, activation, LIVE/PAPER operation, or real OANDA mutation.
- **Regression evidence required:** Focused deterministic owner-loss-after-TP-claim test proving zero dependent PUTs; existing P05 protection and runtime tests remain green; changed-slice Ruff/Pyright and `git diff --check` pass.

## Worker Evidence

- **Status:** `DONE`
- **Implementation:** `PaperDurableExecutionApplication` now re-runs the supplied
  owner/generation mutation guard after the committed Take Profit claim and its
  runtime cycle callback, immediately before the protection seam can dispatch
  the dependent PUT. Guard loss raises the existing mutation barrier, retains
  the claim, and prevents the PUT.
- **Regression coverage:** Added deterministic `httpx.MockTransport` coverage
  for owner loss in the committed-claim-to-PUT window; the claim is retained
  and only the entry POST is observed. Existing same-process protection coverage
  remains green.
- **Checks:**
  - `uv run pytest backend/tests/runtime/test_runtime_completion_cross_seam.py backend/tests/paper/test_durable_execution.py backend/tests/integrations/test_oanda_protection_completion.py backend/tests/runtime/test_runtime_orchestration.py -q` — `52 passed`
  - `uv run ruff format --check backend/paper/durable_execution.py backend/tests/runtime/test_runtime_completion_cross_seam.py` — passed
  - `uv run ruff check backend/paper/durable_execution.py backend/tests/runtime/test_runtime_completion_cross_seam.py` — passed
  - `uv run pyright backend/paper/durable_execution.py backend/tests/runtime/test_runtime_completion_cross_seam.py` — `0 errors, 0 warnings, 0 informations`
  - `git diff --check` — passed
- **Capital safety:** No credentials, activation, PAPER/LIVE operation, or real
  OANDA mutation used.
