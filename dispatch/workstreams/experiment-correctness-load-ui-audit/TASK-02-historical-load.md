# TASK-02 Receipt — Historical loading

## Scope completed

- OANDA native M15 requests now use half-open windows of at most 60,000 minutes
  (4,000 M15 candles); M1 requests remain bounded at 4,000 minutes (4,000
  candles). Native analytical data remains OANDA M15 MID and execution data
  remains independent M1 BID/ASK.
- Initial coordinator planning now uses the StrategyVersion's declared
  `required_historical_context_bars` rather than the fixed 25-hour estimate.
- V2 acquisition accepts a progress callback and reports progress only after the
  execution range has been committed. Progress is durably retained in the
  existing load coverage JSON with phase, completed/total units, unit, and
  fetched/committed range counts; completed units are monotonic.
- Status payloads expose the additive progress facts without changing terminal
  lifecycle authority or enabling completion early.

## Changed application files

- `backend/integrations/oanda/source.py`
- `backend/market_data/historical_load.py`
- `backend/market_data/ingestion.py`
- `backend/persistence/historical_data_load_repository.py`
- `backend/api/historical_data.py`
- `backend/tests/integrations/test_oanda_source.py`

## Validation / evidence

- `pytest -q backend/tests/test_historical_data_load.py backend/tests/integrations/test_oanda_source.py`
  — **37 passed, 1 skipped** (the skipped test requires configured PostgreSQL).
- `ruff check` on all changed backend modules/tests — **passed**.
- `python -m compileall -q backend/market_data backend/integrations/oanda
  backend/persistence backend/api` — **passed**.
- Deterministic fake HTTP transport evidence: the M1 4,001-minute case made 2
  provider requests with the first window ending at 4,000 minutes; the native
  M15 60,001-minute case made 2 requests with the first window ending at
  60,000 minutes. Retry behavior remains bounded to 3 attempts per window.
- No real OANDA call or credential was used. Wall-clock timings were not
  recorded by the existing unit transport and therefore no timing claim is
  made.

## Limitation / follow-up

The existing immutable V2 snapshot persistence seam does not yet provide a
safe union operation for extending an already-created snapshot's native M15
and execution memberships. The coordinator still has its pre-existing
warm-up extension loop, so an observed shortfall can repeat an enlarged
acquisition. This receipt deliberately does not approximate that requirement
with a partial snapshot or mutate an existing snapshot; a follow-up must add a
focused immutable union/prefix-membership operation before claiming full
no-refetch extension evidence.

No Git commands were run.
