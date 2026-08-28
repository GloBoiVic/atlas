# T020 — Final bounded V2 path

Status: `DONE_WITH_CONCERNS`

Resolve only the remaining T018/T019 validation findings: replace authoritative V2
`current_bars` full-range tuple materialization with bounded ordered streaming/frontier
coverage, bound execution acquisition metadata (no request-sized list), remove or
constrain compatibility fallbacks from the V2 path, and make deterministic fixture
repeat fingerprint/membership equivalence real rather than placeholder/different.

## Validation remediation

Remove the remaining authoritative V2 `current_bars` tuple materialization and
tuple-accumulated planning path identified by VALIDATE. Ensure compatibility fallbacks
cannot be selected by V2. Preserve bounded ordered semantics and add source/regression
coverage before any further long live run.
Preserve sparse M1/native M15 semantics, immutable snapshots, and crash safety. Add
regressions and telemetry for max batch/progress payload/RSS. Do not start genuine
multi-hour OANDA validation until these source-audit findings are resolved.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T020-final-bounded-v2-path.md`  
FILES CHANGED: `backend/market_data/ingestion.py`, `backend/market_data/freeze03_benchmark.py`, `backend/tests/market_data/test_freeze03_regressions.py`  
CHECKS / EVIDENCE: `pytest -q backend/tests/market_data/test_freeze03_regressions.py backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/integration/test_market_data_ingestion.py` — 15 passed, 5 skipped; `git diff --check`; `python -m compileall -q backend/market_data backend/tests/market_data/test_freeze03_regressions.py`. `_coverage_product` now uses `current_bars_stream`; V2 snapshot membership requires `current_bar_rows_stream` with no execution-stream compatibility fallback; V2 planning yields coalesced windows without tuple `+=`; source regression rejects authoritative tuple/list/set/all calls and planning accumulation. Existing bounded telemetry remains: max batch 2868, max progress payload 415 bytes, fixture covered-repeat provider calls 0.
FINDINGS / CONCERNS: Genuine OANDA/PostgreSQL full-calendar-year benchmark remains blocked by missing account configuration per latest VALIDATION.md and must not be started. Fixture “year” remains the existing representative month and is not benchmark-gate evidence. Legacy non-authoritative APIs retain tuple materialization by design and were not changed. Before acceptance, rerun VALIDATE source audit and the credentialed fresh-process OANDA/PostgreSQL benchmark when account ID is safely configured.
