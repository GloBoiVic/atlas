# TASK-06 Receipt — R1 Remediation

## Status

Implemented the bounded remediation for R1-001, R1-002, R1-003, R1-005, and the
changed Experiment workflow formatting. Database/OANDA acceptance was not
attempted.

## Changes

- Terminal close now requires an executable observation ending exactly at the
  requested experiment end and at/after entry; entry-only and pre-end sparse
  observations fail closed with `EXECUTION_DATA_UNAVAILABLE`.
- V2 coverage now checks the complete expected native M15 frontier sequence,
  including internal frontiers, and reports `MISSING_ANALYTICAL_FRONTIERS`
  instead of silently omitting them.
- Result quality now classifies material blocked gaps affecting the requested
  period as `DEGRADED`; non-material/sparse diagnostics remain `DETERMINED`.
  Failed Experiments return an explicit `FAILED` quality state through the API.
- The persisted result-quality constraint and migration accept `DEGRADED`.
- Normal Experiment API labels use the requested date period rather than a raw
  UUID fragment; technical IDs remain available separately.
- The existing changed Experiment workflow file was formatted with Prettier.

## Regression coverage

Added deterministic checks for entry-only terminal absence, pre-end terminal
absence, material versus non-material quality, and an internal native M15 gap.

## Verification

- Targeted runner/clock/configuration/results tests: passed (30 tests across
  the completed targeted runs).
- Ruff over changed backend implementation/tests: passed.
- Backend compileall: passed.
- Frontend typecheck, lint, and Prettier check for the changed workflow: passed.
- The combined targeted command exceeded the 120-second tool timeout, but its
  separately completed suites passed and the results suite passed in 183s.

No environment files, credentials, database, OANDA account, or other dispatch
artifacts were modified. No Git commands were run.
