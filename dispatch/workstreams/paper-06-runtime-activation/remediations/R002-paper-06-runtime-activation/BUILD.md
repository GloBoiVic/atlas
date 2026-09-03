# R002 — Executable runtime orchestration wiring

- **Remediation ID:** `R002-paper-06-runtime-activation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin finding and source artifact:** `VALIDATION.md` `CRITICAL-02 — The executable atlas-runtime process never runs the orchestrator`
- **Finding severity:** `CRITICAL`
- **Related original task(s):** T006, T008
- **Approved requirement or invariant violated:** ARCHITECTURE §§1, 7.1–7.2, 8.1, 9.3, 12.1 — the supported executable local process must construct and run the approved `PaperRuntimeOrchestrator` with one owner, fixed cadence, startup recovery, and idle-without-activation behavior; process liveness alone must never create activation authority.
- **Exact remediation outcome:** Give the `atlas-runtime` executable a safe production construction and loop path for the existing `PaperRuntimeOrchestrator` and its already-approved OANDA Practice/native frontier, account, P05 execution, and reconciliation seams. Preserve `--check`, startup database readiness handling, signal shutdown, explicit activation requirement, and idle behavior with no activation/provider mutation. Add deterministic injectable construction/loop coverage proving the executable invokes orchestrator startup/ticks without real broker calls.
- **Affected implementation seams:** `backend/runtime/main.py`, existing runtime/orchestration/ownership interfaces, existing OANDA source/account/PAPER 05/reconciliation constructors, and focused runtime entrypoint tests. Keep construction explicit and local; do not introduce generic worker/scheduler infrastructure.
- **Explicit out-of-scope items:** No lifecycle/authority semantic redesign, new activation behavior, automatic activation, catch-up, retries, broker mutation changes, Risk-policy change, API/frontend work, schema/migration changes, credentials, activation, LIVE/PAPER operation, or real OANDA mutation.
- **Regression evidence required:** `atlas-runtime --check` remains readiness-only and exits safely; injected executable loop exercises startup/tick and stops on signal/event; no-activation path remains idle with no provider calls; focused runtime/orchestration regressions, changed-slice Ruff/Pyright, and `git diff --check` pass.

## Worker Evidence

- **Status:** `DONE`
- Added explicit `create_runtime_orchestrator(...)` production composition for the
  native OANDA Practice M15 source, current account reader, PAPER 05 durable
  execution/protection seams, bounded reconciliation, and the dedicated runtime
  owner.
- `run(...)` now creates the session factory and invokes the injected/default
  orchestrator loop only after database readiness and outside `--check`; signal
  and event shutdown, idle-without-activation behavior, and sanitized failure
  handling remain bounded.
- Added deterministic entrypoint tests for injected loop invocation, `--check`
  non-construction, idle startup/tick with zero provider reads, and supported
  OANDA/PAPER 05 construction wiring. No broker request or activation was used.
- **Focused tests:** `uv run pytest backend/tests/test_runtime.py backend/tests/runtime/test_runtime_orchestration.py backend/tests/runtime/test_runtime_cycles.py backend/tests/runtime/test_runtime_completion_cross_seam.py backend/tests/paper/test_execution_composition.py -q` — `60 passed`.
- **Changed-slice Ruff:** `uv run ruff format --check backend/runtime/main.py backend/tests/test_runtime.py` and `uv run ruff check backend/runtime/main.py backend/tests/test_runtime.py` — passed.
- **Changed-slice Pyright:** `uv run pyright backend/runtime/main.py backend/tests/test_runtime.py` — `0 errors, 0 warnings, 0 informations`.
- **Diff safety:** `git diff --check` — passed.
- **Capital safety:** no credentials, activation, PAPER/LIVE operation, or real
  OANDA mutation was performed.
