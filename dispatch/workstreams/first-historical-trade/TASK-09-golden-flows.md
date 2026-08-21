# TASK-09 — Real EMA golden flows

Status: DONE

## Changes

- Added PostgreSQL-backed LONG and SHORT acceptance fixtures with complete,
  immutable OANDA EUR/USD M1 MID/BID/ASK membership.
- Registered the persisted EMA Sweep Engulfing StrategyVersion from its real
  source archive and supplied actual reference, sweep, confirmation, and
  post-decision quote inputs; no stub decision path is used.
- Added acceptance coverage for provenance, M15 frontier/no signal-bar reuse,
  immutable TradeIntent, approved PRE_FLIGHT/PRE_SUBMISSION Risk, executable
  quote sides, source M1 identities, actual-entry target, Fill-driven closed
  Trade/P&L/R, account and FLAT Position projections, COMPLETED Experiment,
  and semantic rerun equivalence excluding generated identity/timestamps.
- Updated the existing SimulationClock boundary to skip the scheduled NY
  daily-break frontier when no completed M1 exists; it remains fail-closed for
  missing data during an open session.

## Validation receipts

- `pytest -q backend/tests/integration/test_golden_flows.py` — **2 passed**
  against PostgreSQL.
- `pytest -q backend/tests/integration/test_golden_flows.py
  backend/tests/experiments/test_clock.py` — **5 passed**.
- `ruff check backend/experiments/clock.py
  backend/tests/integration/test_golden_flows.py` — **passed**.
- `pyright backend/experiments/clock.py
  backend/tests/integration/test_golden_flows.py` — **0 errors, 0 warnings, 0
  informations**.
- No Git-changing commands were run.

## PHASE3_OPEN_CHECKPOINT_V1 exclusions

The golden evidence deliberately stops after the first completed target Trade.
It excludes full M1 replay, intrabar ambiguity ordering, gaps, slippage, costs,
equity history, metrics, forced-end close, and multiple trades. It adds no API,
UI, CLI, runtime, OANDA, PAPER/LIVE, reconciliation, or generalized
infrastructure. These remain Phase 4/deferred behavior and are not fabricated
by this task.

## Material conflicts

- The existing runner records entry source M1 identities in intent rationale,
  while the current schema has no separate source-identity table; the test
  verifies those identities resolve to immutable snapshot members.
- The existing simulated target contract persists the target price as the
  exit Fill price; executable-side correctness is proven through the
  post-decision BID/ASK quote and direction-specific target observation.

## Terminal status

DONE only when both parameterized LONG and SHORT PostgreSQL golden flows pass.
