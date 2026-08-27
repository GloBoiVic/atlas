# T003 — V2 completion and deterministic metrics

Status: `BUILD COMPLETE`

## Implementation receipt

- Canonical equity metrics now consume persisted sequence order directly; no
  timestamp sorting or forward-fill is used. Daily Sharpe endpoints are the
  final canonical point per UTC day, with starting capital as the first base,
  sample deviation, zero risk-free rate, and `sqrt(252)` annualization.
- V2 completion now persists all seven metric `{state,value,unit,reason}`
  projections, stable metric-state schema, Sharpe methodology in the output
  fingerprint, and result quality. Material gaps take precedence over
  conservative dual-touch ambiguity.
- Fingerprints now include metric schema, Sharpe methodology, and quality in
  addition to immutable inputs and simulation facts.
- Updated regression coverage for canonical ordering and metric edge cases.

Files changed: `backend/experiments/metrics.py`,
`backend/experiments/metric_contract.py`, `backend/experiments/runner.py`,
`backend/tests/experiments/test_metrics.py`.

Checks: `python -m compileall -q backend/experiments backend/persistence`;
`pytest -q backend/tests/experiments/test_metrics.py
backend/tests/experiments/test_result_state.py
backend/tests/experiments/test_runner_diagnostics.py` (21 passed);
`git diff --check`.

Concerns: the completion method retains its legacy `_complete_phase4` name for
compatibility; T004 owns switching read paths to the persisted result. Existing
legacy comparison callers may still calculate metrics outside the V2 completion
seam.
