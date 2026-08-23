# TASK-06 — FastAPI contract and composition

- **Task:** Implement approved blueprint task 6 only: Pydantic v2 HTTP contracts,
  Experiment routes, request-scoped sessions, error translation, composition,
  injectable app dependencies, and OpenAPI exposure.
- **Agent:** backend builder
- **Model:** gpt-5.6-luna (`openai/gpt-5.6-luna`)
- **Branch:** `feature/phase-5-experiment-workflow`

## Changed files

- `backend/api/app.py`
- `backend/api/experiments.py`
- `backend/api/schemas.py`
- `backend/tests/integration/test_api_experiments.py`

## Outcome

Added the `/api/v1/experiments` contract for configuration options, coverage
validation, create, list/detail polling, synchronous retry-safe run, equity,
Trade list, and Trade detail. Request models use Pydantic v2 with camelCase
aliases, strict unknown-field rejection, bounded inputs, and decimal financial
inputs. Response composition preserves decimal strings and UTC RFC 3339 values.

Added request-scoped SQLAlchemy sessions, explicit service/registry/runner
composition, injectable app-factory dependencies, sanitized validation and
domain/infrastructure error envelopes, and generated FastAPI OpenAPI routes.
Health routes remain unchanged.

The HTTP integration regression starts a real gated synchronous run, issues a
separate concurrent GET request, and observes durable `RUNNING` before releasing
the run. No background task, worker, queue, Redis, or additional process was
introduced. Unknown Experiment IDs are mapped to 404 before lifecycle execution.

## Exact validation receipts

- `ruff check backend/api/app.py backend/api/experiments.py backend/api/schemas.py backend/tests/integration/test_api_experiments.py` → **All checks passed**.
- `python -m py_compile backend/api/app.py backend/api/experiments.py backend/api/schemas.py backend/tests/integration/test_api_experiments.py` → **passed**.
- `.venv/bin/pytest -q backend/tests/test_api_health.py` → **4 passed**; existing health behavior and engine disposal preserved.
- `.venv/bin/pytest -q backend/tests/integration/test_api_experiments.py` → **1 passed** against `ATLAS_TEST_DATABASE_URL`; HTTP-gated RUNNING visibility and terminal response proven.

## Evidence scope

Receipts cover API composition, request validation, health regression,
request-scoped status polling during synchronous execution, durable lifecycle
visibility, and sanitized route-level response composition. OpenAPI is generated
from the mounted FastAPI router; no parallel frontend contract was added.

## Blocker/conflict

None. No Git mutations were performed. Existing dispatch artifacts and preceding
task changes remain untouched.

## R1 remediation — timestamp normalization and cursor pagination

Repaired only the three blocking review defects:

1. `version_to_domain` now canonicalizes aware persisted timestamps with
   `astimezone(UTC)` and treats a naive persisted timestamp as the documented
   UTC storage representation, without guessing local wall time. API timestamp
   serialization uses the same explicit normalization, so DB-session timezone
   offsets cannot leak into the contract.
2. All API timestamp paths routed through `_utc`/`_json` now emit RFC3339 UTC
   `Z`, including create/detail/list/status, equity, Trade, chart, coverage, and
   provenance timestamps.
3. Experiment listing now uses an opaque base64url JSON cursor containing the
   canonical timestamp and UUID, applies a keyset predicate for
   `(created_at DESC, id DESC)`, rejects malformed cursors, and preserves the
   1–100 limit bound. Equal-created-at rows are covered by the integration
   pagination test.

Added HTTP contract coverage for fresh-session create, naive timestamp domain
normalization, UTC-Z timestamps, first/next/final cursor pages, equal-created-at
UUID tie-breaking, invalid cursors, and limit bounds. No unrelated code,
background execution, or Task 7 work was added.

### Exact remediation validation receipts

- `ruff check backend/api/app.py backend/api/experiments.py backend/api/schemas.py backend/persistence/strategy_repository.py backend/persistence/result_repository.py backend/experiments/results.py backend/tests/integration/test_api_experiments.py` → **All checks passed**.
- `python -m py_compile backend/api/app.py backend/api/experiments.py backend/api/schemas.py backend/persistence/strategy_repository.py backend/persistence/result_repository.py backend/experiments/results.py backend/tests/integration/test_api_experiments.py` → **passed**.
- `.venv/bin/pytest -q backend/tests/integration/test_api_experiments.py` → **3 passed**; fresh-session create, naive persisted timestamp normalization, UTC-Z contract, and keyset cursor pagination.
- `.venv/bin/pytest -q backend/tests/integration/test_api_experiments.py backend/tests/integration/test_experiment_lifecycle.py backend/tests/integration/test_experiment_configuration.py` → **10 passed**.
- `.venv/bin/pytest -q backend/tests/test_api_health.py backend/tests/experiments/test_results.py backend/tests/experiments/test_metrics.py backend/tests/experiments/test_configuration.py` → **22 passed**.
- `.venv/bin/pytest -q backend/tests/strategies/test_provenance.py backend/tests/integration/test_strategy_persistence.py backend/tests/integration/test_golden_flows.py` → **20 passed**.

A combined command that placed `test_api_health.py` before PostgreSQL integration
tests was not used as evidence: the pre-existing settings-cache test interaction
left the integration migration pointed at the health test URL. The same relevant
tests pass in isolated, correctly configured invocations above.

No Git mutations were performed.
