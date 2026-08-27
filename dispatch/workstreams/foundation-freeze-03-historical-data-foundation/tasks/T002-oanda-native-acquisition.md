# T002 — OANDA native acquisition

Status: `DONE`

Implement the OANDA adapter/provider acquisition contract for native M15 MID and M1
BID/ASK, with granularity-appropriate bounded windows, pagination/request parameters,
UTC normalization, complete-observation filtering, and safe redacted failures. Add
focused tests. Do not implement durable coordinator lifecycle or snapshot authority.

## Receipt

- Implemented/verified the narrow OANDA Practice adapter contract for native
  `M15/MID` analytical candles and `M1/BID+ASK` execution observations. Existing
  adapter behavior uses EUR/USD, RFC3339 UTC `from`/`to`, OANDA `price` and
  `granularity` parameters, `smooth=false`, and bounded internal windows of
  60,000 minutes for M15 and 4,000 minutes for M1. Large ranges are paginated
  into those windows without a request-count/research ceiling.
- Preserved half-open response filtering, UTC timestamp normalization, sorted
  duplicate collapse, conflicting duplicate rejection, complete-only canonical
  bars, explicit incomplete observations, native M15 quarter-hour validation,
  Decimal OHLC handling, bounded retries, and redacted provider failures.
- Hardened normalization to reject provider timestamps containing seconds or
  microseconds before they can become canonical minute observations.
- Added deterministic coverage for the M1 timestamp-alignment failure path.

Checks/evidence:

- `pytest -q backend/tests/integrations/test_oanda_source.py backend/tests/integrations/test_oanda_external.py`
  → 24 passed, 1 skipped (credentialed external smoke test).
- `python -m compileall -q backend/integrations/oanda/source.py backend/tests/integrations/test_oanda_source.py`
  → passed.
- `git diff --check` → passed.

Scope/concerns: no durable coordinator lifecycle, snapshot authority, or
unrelated cleanup was changed. The external OANDA test remains intentionally
skipped without credentials and an explicit bounded test range.
