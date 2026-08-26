# TASK-03 — API / Results Builder

- **Task:** Expose persisted proposal policy/status/expiry and generic structured
  evidence/landmarks through the existing Experiment result APIs.
- **Agent:** API/results builder
- **Model:** `opencode/gpt-5.6-luna`
- **Outcome:** COMPLETE (integration fixture environment remains unavailable)

## Changed files

- `backend/experiments/results.py` — consumes persisted `setup_facts`, generic
  evidence, and landmarks; adds read-only proposal policy/status/expiry payloads
  to Trade detail and price analysis; adds execution landmarks and keeps all
  financial values as decimal strings without rerunning Strategy.
- `backend/api/schemas.py` — added response models and optional stable
  `evidence`, `landmarks`, `proposalDiagnostics`, and `setupFacts` fields while
  preserving existing price-analysis fields and aliases.

## Validation receipts

- `python -m compileall -q backend/experiments/results.py backend/api/schemas.py backend/api/experiments.py`
  — passed.
- `python -m pytest backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py -q`
  — **36 passed**.
- `python -m pytest backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py backend/tests/integration/test_api_experiments.py -q`
  — **37 passed, 8 errors**; integration fixtures require the absent
  `ATLAS_TEST_DATABASE_URL` environment variable. No application assertion
  failed before fixture setup.

## Concerns / receipts

- TASK-02 follow-up receipt confirms `setup_facts`, generic `evidence`, and
  generic `landmarks` are now persisted in immutable rationale. The reader
  consumes those values directly and does not detect patterns or rerun Strategy.
- Existing endpoint paths, completion gates, FAILED/incomplete errors,
  pagination, and immutable read semantics were left unchanged.
- No strategy pattern detection, dependency, persistence compatibility layer,
  or frontend change was introduced.

## Follow-up receipt — validation blocker, attempt 1

- **Outcome:** DONE.
- Updated `backend/api/experiments.py` configuration-options selection to use
  exact registry/provenance availability rather than an implementation-key
  `.v2` suffix allowlist. Unavailable obsolete catalog rows are omitted; the
  registered current Strategy is exposed. The display architecture label is
  now generic (`HISTORICAL_EXECUTION`).
- Validation command:
  `python -m pytest backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py backend/tests/experiments/test_configuration.py -q`
- Result: **38 passed, 1 failed**. The failure is the pre-existing
  `test_production_registration_archives_once_and_evaluation_has_no_path_input`,
  which still requests removed `ema_sweep_engulfing.v1`; it is outside this
  API/results ownership and cannot be changed here.

## Follow-up receipt — validation blocker, attempt 2 (final bounded fix)

- **Root cause:** `/price-analysis` returned HTTP 500 during FastAPI response
  validation. Persisted Confirmation Break setup facts intentionally include
  `trendRelation`, `atr`, `stopPrice`, and `triggerPrice`, but the strict
  legacy `PriceAnalysisFactResponse` rejected those fields as extras. The
  traceback is recorded in `/tmp/atlas-api-final-validation.log` at lines
  174–218.
- **Fix:** `PriceAnalysisFactResponse` now declares the persisted setup fields;
  results continue to consume persisted generic evidence/landmarks and do not
  rerun or detect Strategy patterns. Result detail/list identity now derives
  from the persisted `StrategyVersionModel` and related catalog Strategy
  (`strategy_key`, name, version, implementation key, source fingerprint),
  replacing obsolete identity assumptions.
- **Validation:**
  `python -m compileall -q backend/experiments/results.py backend/api/schemas.py backend/api/experiments.py`
  — passed.
- **Validation:**
  `python -m pytest backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py -q`
  — **36 passed**.
- **Outcome:** DONE. No remaining API/results blocker identified. Full
  integration validation still depends on the separately documented
  `ATLAS_TEST_DATABASE_URL` environment prerequisite.

## Follow-up receipt — API integration classification

- **Classification:** DONE. The latest TASK-02 receipt confirms the current
  Confirmation Break v1 fixtures and persisted generic evidence/landmarks;
  no API-side obsolete golden data or compatibility path remained to restore.
- **Historical failure diagnosis:** the prior `/price-analysis` 500 was a
  FastAPI `ResponseValidationError` caused by strict reference-fact schemas
  rejecting persisted `trendRelation`, `atr`, `stopPrice`, and `triggerPrice`.
  The schema fix is present and the result identity path uses persisted
  StrategyVersion/catalog data.
- **Exact validation command:**
  `ATLAS_TEST_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' ATLAS_DATABASE_URL='postgresql+psycopg://atlas:atlas@127.0.0.1:5432/atlas_test' python -m pytest backend/tests/experiments/test_results.py backend/tests/experiments/test_price_analysis_results.py backend/tests/integration/test_api_experiments.py -q`
- **Result:** **45 passed, 4 warnings**. Warnings are the existing Starlette
  httpx deprecation and unregistered `price_analysis` pytest mark; no test
  failures or environment setup errors occurred.
- **Outcome:** DONE. No remaining API/results blocker.
