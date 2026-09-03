# VALIDATION — Dogfood 01 PAPER Activation Response Projection Remediation

## Dispatch

- **Role:** `VALIDATE`
- **Workstream:** `dogfood-01-paper-activation-response-projection`
- **Branch:** `solo/dogfood-01-paper-activation-response-projection`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Task:** `T001`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-paper-activation-response-projection/VALIDATION.md`
- **Specialist skills:** `tdd`

## Independent verdict

**PASS.** T001 satisfies the frozen projection, response-path, decimal-string,
identity, and safety acceptance criteria. No product regression was found.

## Evidence reviewed

- `PLAN.md` and `ARCHITECTURE.md` require the narrow outbound repair only:
  `PaperRuntimeActivation.to_json()` must emit the existing UTC-normalized
  `requested_at`; response models and all runtime seams remain frozen.
- The T001 receipt describes the same production/test scope and reports the
  focused checks below.
- The actual tracked branch diff contains one production-line addition in
  `backend/runtime/persistence_contracts.py`, focused real-projection coverage
  in `backend/tests/test_api_paper.py`, and the operational `dispatch/ACTIVE.md`
  update. No schema, route, repository, migration, Risk, execution, runtime, or
  provider file changed.
- `PaperRuntimeActivation.to_json()` now emits
  `self.requested_at.isoformat().replace("+00:00", "Z")`; `requested_at` remains
  absent from `immutable_json()`.
- The API test constructs a real `PaperRuntimeActivation` and routes real
  `PaperRuntimeActivationResult`, `PaperRuntimeStatus`, and activation
  projections through `TestClient` for create, active, detail/status, and stop.
  It asserts HTTP 200, exact `2026-09-03T12:00:00Z` `requestedAt`, and string
  `riskPerTrade` with canonical value `"0.01"` on every required path.

## Checks and results

Repository and diff inspection:

```text
pwd; git rev-parse --show-toplevel; git branch --show-current; git status --short; git log -1 --oneline
/Users/vike/Desktop/atlas
/Users/vike/Desktop/atlas
solo/dogfood-01-paper-activation-response-projection
 M backend/runtime/persistence_contracts.py
 M backend/tests/test_api_paper.py
 M dispatch/ACTIVE.md
?? dispatch/workstreams/dogfood-01-paper-activation-response-projection/
4a737af Close PAPER 06 workstream
```

```text
git diff --name-status; git diff --check; git diff --numstat
M	backend/runtime/persistence_contracts.py
M	backend/tests/test_api_paper.py
M	dispatch/ACTIVE.md
1	0	backend/runtime/persistence_contracts.py
82	58	backend/tests/test_api_paper.py
9	1	dispatch/ACTIVE.md
```

`git diff --check` passed with no output. The production diff is exactly the
authorized `requested_at` projection addition.

Focused projection and response paths:

```bash
uv run pytest backend/tests/test_api_paper.py -k 'real_activation_projection or routes_project_all_control_and_status_seams'
```

```text
2 passed, 5 deselected, 1 warning in 1.98s
```

Reconciled focused command:

```bash
uv run pytest backend/tests/test_api_paper.py backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_persistence.py backend/tests/runtime/test_runtime_risk_precision.py
```

```text
60 passed, 1 warning in 2.48s
```

Static checks on changed application/test files:

```bash
uv run ruff format --check backend/runtime/persistence_contracts.py backend/tests/test_api_paper.py
# 2 files already formatted

uv run ruff check backend/runtime/persistence_contracts.py backend/tests/test_api_paper.py
# All checks passed!

uv run pyright backend/runtime/persistence_contracts.py backend/tests/test_api_paper.py
# 0 errors, 0 warnings, 0 informations
```

Runtime-process observation:

```bash
pgrep -x atlas-runtime || true; pgrep -f '[u]vicorn.*atlas' || true
# no output
```

## Findings

| Classification | Type | Finding | Impact |
| --- | --- | --- | --- |
| PRODUCT | DEFECT | None observed; the missing real `requestedAt` projection is repaired. | None |
| REGRESSION | DEFECT | None observed; focused API, activation, persistence, and risk-precision checks passed. | None |
| TOOLING | NEW SCOPE | TestClient reports the existing Starlette/httpx deprecation warning. | Non-blocking; unrelated to this diff. |
| TOOLING | NEW SCOPE | T001 header still says `Status: READY`, while its completion receipt and PLAN say `DONE`. | Evidence metadata inconsistency only; not an application defect. Not repaired by VALIDATE. |

## Capital-safety evidence and limitations

- All checks used deterministic fakes and in-memory FastAPI `TestClient` routes;
  the service fixture was not the production service and opened no database.
- No `atlas-runtime` start, real durable PAPER activation, existing Dogfood 01
  activation mutation, credentialed OANDA request, broker mutation, or other
  capital-capable action was performed. The route POSTs exercised only the fake
  service response projection.
- The diff contains no changes to activation transaction/lifecycle/idempotency,
  Risk, execution, reconciliation, persistence schema/migrations, or provider
  seams. The existing `REQUESTED`/`IDLE`/`FRESH_BOOTSTRAP` and replay/identity
  guards remained green in the focused suite.
- No integration database or external-provider checks were run; they are not
  required for this projection-only repair and would exceed the frozen safe
  deterministic validation boundary.
