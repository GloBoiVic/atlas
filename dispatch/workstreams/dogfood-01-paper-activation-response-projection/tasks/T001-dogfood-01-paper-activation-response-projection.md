# T001 — Restore PAPER activation response projection

- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `dogfood-01-paper-activation-response-projection`
- **Branch:** `solo/dogfood-01-paper-activation-response-projection`
- **Depends on:** none
- **Owned artifact:** this file

## Objective

Implement only the approved projection repair: make the real
`PaperRuntimeActivation.to_json()` emit its existing durable `requested_at` value
using the established UTC ISO-8601 `Z` convention, and add focused deterministic
regression coverage for the domain projection and create, active, detail/status,
and stop response paths.

## Required boundaries

- Change production code only in `PaperRuntimeActivation.to_json()` for this repair.
- Keep `PaperRuntimeActivationResponse` strict and required; do not alter response
  envelopes or aliases.
- Keep `requested_at` excluded from `immutable_json()` and preserve same-ID replay,
  immutable identity, lifecycle, transaction, and durable `REQUESTED` semantics.
- Preserve exact Decimal ingestion and the existing canonical decimal-string
  `riskPerTrade` response behavior; introduce no float conversion.
- Use fixed UUIDs, fixed timezone-aware time, and fakes/TestClient only.
- Do not start `atlas-runtime`, contact OANDA, create or modify any activation, or
  perform broker/capital-capable operations.
- Do not change persistence schema/migrations, Risk, execution, reconciliation,
  runtime, broker, or provider behavior.

## Evidence required

- A real `PaperRuntimeActivation` projection contains exact `requested_at` and
  validates through `PaperRuntimeActivationResponse`.
- Alias serialization contains `requestedAt` as a string and keeps `riskPerTrade`
  as a JSON string with existing canonicalization.
- Deterministic HTTP coverage proves HTTP 200, exact `requestedAt`, and string
  `riskPerTrade` for create, active, detail/status, and stop.
- Relevant existing guards remain green, including replay/identity and lifecycle
  semantics where covered by the focused tests.
- Run the focused command from the reconciled ARCHITECTURE when applicable and
  record exact results below.

## Completion receipt

- **Status:** `DONE`
- **Implementation:** Restored `requested_at` in
  `PaperRuntimeActivation.to_json()` from the already UTC-normalized
  `self.requested_at` using the established ISO-8601 `Z` convention. Replaced the
  manual API payload fixture with real `PaperRuntimeActivation`,
  `PaperRuntimeActivationResult`, and `PaperRuntimeStatus` projections, and added
  direct domain projection/response-model regression assertions.
- **Files changed:**
  - `backend/runtime/persistence_contracts.py`
  - `backend/tests/test_api_paper.py`
- **Checks/evidence:**
  - TDD red: before the production repair, the two new projection/path tests
    failed because `requested_at` was missing from the real projection and FastAPI
    response validation reported the required `requestedAt` field missing.
  - `uv run pytest backend/tests/test_api_paper.py -k 'real_activation_projection or routes_project_all_control_and_status_seams'` — **2 passed, 1 warning**.
  - `uv run pytest backend/tests/test_api_paper.py backend/tests/runtime/test_runtime_activation.py backend/tests/runtime/test_runtime_persistence.py backend/tests/runtime/test_runtime_risk_precision.py` — **60 passed, 1 warning**.
  - `uv run ruff format --check backend/runtime/persistence_contracts.py backend/tests/test_api_paper.py` — **2 files already formatted**.
  - `uv run ruff check backend/runtime/persistence_contracts.py backend/tests/test_api_paper.py` — **All checks passed**.
  - `uv run pyright backend/runtime/persistence_contracts.py backend/tests/test_api_paper.py` — **0 errors, 0 warnings, 0 informations**.
  - Deterministic coverage uses fixed UUIDs, fixed `2026-09-03T08:00:00-04:00`,
    verifies exact projected `2026-09-03T12:00:00Z`/`requestedAt`, preserves
    canonical decimal text `0.01` as a JSON string, and confirms `requested_at`
    remains outside `immutable_json()` across create, active, detail/status, and
    stop routes.
- **Concerns:** One pre-existing non-blocking Starlette/httpx deprecation warning
  appears in TestClient runs. The initial `git status` also showed unrelated
  `dispatch/ACTIVE.md` changes; that file was not modified by this task. No
  runtime, database activation, OANDA request, broker mutation, capital-capable
  action, schema/migration, lifecycle, idempotency, Risk, execution,
  reconciliation, or provider behavior was changed.
