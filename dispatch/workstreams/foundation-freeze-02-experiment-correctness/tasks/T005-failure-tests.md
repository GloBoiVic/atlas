# T005 — Failure taxonomy and behavioral regression evidence

Status: `BUILD COMPLETE`

Scope after approval: classify Strategy, market-data, Risk, execution,
accounting/invariant, and persistence failures at the smallest useful typed
boundary, then add public/domain regression coverage for the approved contract.
Expected evidence includes temporal/executable semantics, protection ambiguity,
costs, terminal equity, quality disclosure, and fail-closed behavior.

## Implementation receipt

- Replaced the V2 runner's broad `ValueError`/`Exception` mapping with a small
  typed boundary: Strategy domain errors, execution contract errors, SQLAlchemy
  persistence errors, unsupported Strategy lookup, and validation/market-data
  input failures now retain distinct categories and sanitized details.
- Preserved durable `_fail` behavior and the lifecycle's last-resort persistence
  fallback. No new exception framework or full-fill simulation changes were
  introduced.
- Added quality precedence coverage: material data uncertainty yields
  `DEGRADED`, otherwise ambiguity yields
  `CONSERVATIVE_AMBIGUITY_RESOLVED`, otherwise `DETERMINED`.
- Coverage summary: canonical metric ordering and Sharpe edge cases, persisted
  result reads, missing-result/failed behavior, result-state completion guard,
  terminal protection semantics, and quality classification are covered by the
  focused experiment suite. Existing golden execution tests retain ASK/BID,
  protection, costs, terminal close, and deterministic replay coverage.
- Files changed: `backend/experiments/runner.py`,
  `backend/tests/experiments/test_runner_diagnostics.py`.
- Checks: focused experiment tests (33 passed); compileall passed;
  `git diff --check` passed.

Concerns: generic unexpected exceptions still map to the sanitized persistence
fallback by design; a future task may add a narrowly typed accounting/invariant
exception if a concrete domain seam requires one. Existing legacy Phase 4
diagnostic tests remain for reachable compatibility only.
