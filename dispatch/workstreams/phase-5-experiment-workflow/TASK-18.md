# TASK-18 — Trade-detail chart diagnosis and bounded repair

## Outcome

Diagnosed and repaired the local Trade-detail chart composition failure. The
failure was not in Phase 4 aggregation or Strategy behavior.

## Root cause and contract origin

`backend/experiments/results.py:_chart` assumed that `intent.rationale["fields"]`
was an iterable of `(key, value)` pairs. The canonical contract is
`backend/domain/strategy.py:Rationale.to_json`, which serializes the immutable
pair tuple as an object with `dict(self.fields)`. The persisted
`TradeIntentModel.rationale` therefore contains a mapping. Iterating that
mapping directly and unpacking each key caused `ValueError: too many values to
unpack (expected 2)` on the primary completed Trade detail path.

## Fix

- `backend/experiments/results.py` now reads canonical rationale field mappings
  with `.items()` and remains compatible with pair-sequence test fixtures.
- `backend/tests/experiments/test_results.py` now exercises the persisted
  mapping shape and proves the bounded chart includes all strategy time
  markers plus entry and exit annotations.

The fix leaves the existing chart contract intact: immutable DatasetSnapshot
membership is aggregated as canonical M15 MID bars; EMA 100 is calculated from
the progressively available M15 history; strategy reference/sweep/confirmation
times are retained as markers; entry/stop/target/exit price levels remain
provided by the existing Trade-detail level contract; and context selection
remains bounded at 500 candles with an omitted-range disclosure. No Phase 4,
Strategy, or aggregation code was changed.

## Verification

- Focused backend regression:
  `pytest -q backend/tests/experiments/test_results.py`
  **9 passed**.
- Primary E2E:
  `npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'configures, runs' --workers=1`
  **Blocked after the chart fix**: the page reached the Trade 1 detail heading,
  then the existing `FINANCING EXCLUDED` assertion found no matching detail
  content. This is outside the approved chart repair scope.
- Zero-Trade E2E:
  `npx playwright test tests/e2e/experiment-workflow.spec.ts --grep 'zero-Trade' --workers=1`
  **1 passed**.
- Full Phase 5 E2E file:
  `npx playwright test tests/e2e/experiment-workflow.spec.ts --workers=1`
  **3 passed, 1 blocked**; the sole failure is the same primary
  `FINANCING EXCLUDED` assertion.

## Blockers and scope confirmation

The primary and full-suite receipts are not green because of the unrelated
Trade-detail financing-copy assertion. No additional correction was made.
Full validation and review were not run. No dependency, Git state, Phase 4 or
Strategy architecture, database outside the isolated `atlas_test` environment,
or Phase 6 capability was changed; this report is the only dispatch artifact
written for Task 18.
