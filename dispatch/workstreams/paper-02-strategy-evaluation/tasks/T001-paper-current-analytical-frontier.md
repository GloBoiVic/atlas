# T001 — PAPER current analytical frontier

## Assignment

- **Workstream:** `paper-02-strategy-evaluation`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/paper-02-strategy-evaluation`
- **Base SHA:** `7001a91fef1bfc0302b8b579d782654720375520`
- **Depends on:** none
- **Owned application area:** current PAPER analytical-data seam and focused tests
- **Owned artifact:** this task file; update it with the BUILD receipt when complete

## Objective

Implement the narrow current analytical frontier seam required by the approved PLAN. Translate an explicit UTC observation time into one safe completed OANDA EUR/USD M15/MID analytical frontier and the required historical context, returning typed canonical domain data for T002.

Do not implement Strategy resolution/evaluation composition in this task; T002 owns `backend/paper/strategy_evaluation.py` and its Strategy contract orchestration.

## Required behavior

1. Require an explicit timezone-aware UTC `now`; reject naive or non-UTC values rather than normalizing ambiguous input.
2. Floor the acquisition cutoff to the current UTC 15-minute boundary. The forming candle beginning at that cutoff is never requested or used.
3. Use the existing `OandaHistoricalBarSource.fetch_native_m15` seam and canonical `Bar` normalization. Request native EUR/USD M15 MID data only; do not aggregate M1 data.
4. Determine the candidate decision bar as the immediately preceding eligible M15 window under the existing EUR/USD session policy. Do not search backward through a closed session and label an older bar current. If the immediately preceding window is not an eligible/current analytical frontier, return a typed no-frontier/unavailable outcome or fail closed according to existing local conventions.
5. Use the existing `eligible_m15_windows` and `required_warmup_range` helpers to request the required eligible historical range for the candidate. Keep the seam version-neutral; T002 supplies the resolved Strategy requirement/context count.
6. Require sufficient completed history, including the candidate, and reject missing required windows, incomplete provider candles, malformed bars, duplicate starts/ends, conflicting observations, unsupported instrument/resolution/price component, and any bar beyond the acquisition cutoff.
7. Preserve native provider facts as canonical `Bar` values. Never fabricate, forward-fill, interpolate, silently substitute, or derive M15 from M1.
8. Return a small typed result carrying the ordered analytical `Bar` sequence, selected candidate decision `Bar`, and enough frontier/context information for T002 to verify one-frontier progression. Do not create a `StrategyMarketDataRequirement` abstraction; that seam does not exist on current `main`.
9. Do not persist the read or introduce DatasetSnapshot, SimulationClock, ExperimentRunner, historical ExecutionObservation, Risk, execution, runtime, API/UI, or PAPER state ownership.

## Design constraints

- Inspect current source and session-calendar signatures before editing.
- Keep provider payload handling behind the existing OANDA normalization boundary.
- Use existing EUR/USD session-policy semantics; do not add a new calendar or generic market-data framework.
- The returned analytical series must be deterministic for the same source result and cutoff.
- The current frontier is the selected completed bar's `end_time`, not `now`, request time, or processing time.
- If source diagnostics indicate an incomplete or otherwise uncertain required observation, fail closed; do not silently use an older bar.

## Focused tests

Add focused tests in the existing PAPER test area (normally `backend/tests/paper/`) covering at least:

- explicit UTC requirement and 15-minute cutoff;
- forming candle/lookahead exclusion;
- candidate selection at an open eligible window;
- no-current-frontier behavior during a closed session;
- required warm-up range calculation;
- incomplete/missing/duplicate/conflicting/out-of-cutoff/unsupported data rejection;
- native M15-only source invocation and no M1 aggregation;
- deterministic ordered canonical output.

Use fake/recorded provider responses; do not require credentials or a live OANDA call.

## Validation

Run the smallest relevant checks for changed files, including the new focused test file and the existing OANDA/session-calendar tests if affected. At minimum, run:

```bash
uv run pytest backend/tests/paper/test_current_analytical_frontier.py backend/tests/integrations/test_oanda_source.py
uv run ruff format --check <changed backend files>
uv run ruff check <changed backend files>
uv run pyright <changed backend files>
git diff --check
```

Do not run credentialed external checks or add a database integration test for this read-only seam.

## Completion receipt

On completion, update this file with:

- **Status:** `DONE` or `BLOCKED`;
- changed files;
- concise implementation summary;
- focused validation commands and results;
- remaining concerns, if any.

If the required behavior would need persistence, Strategy meaning changes, Risk/execution, runtime authority, or broker mutation, stop `BLOCKED` and report the exact re-scope instead of widening the task.

## BUILD receipt

- **Status:** `DONE`
- **Changed files:**
  - `backend/paper/__init__.py`
  - `backend/paper/current_analytical_frontier.py`
  - `backend/tests/paper/test_current_analytical_frontier.py`
- **Implementation:** Added a version-neutral, dependency-injected native OANDA M15 analytical read. It enforces an explicit UTC acquisition cutoff, selects only the immediately preceding eligible frontier, calculates eligible-session warm-up through the existing calendar helpers, and validates canonical EUR/USD M15 MID completeness, ordering, uniqueness, session membership, and cutoff bounds. It returns typed ordered context/frontier data without Strategy, persistence, Risk, execution, or runtime behavior.
- **Focused validation:**
  - `uv run pytest backend/tests/paper/test_current_analytical_frontier.py backend/tests/integrations/test_oanda_source.py backend/tests/market_data/test_task3.py` — 52 passed.
  - `uv run ruff format --check backend/paper backend/tests/paper/test_current_analytical_frontier.py` — passed.
  - `uv run ruff check backend/paper backend/tests/paper/test_current_analytical_frontier.py` — passed.
  - `uv run pyright backend/paper backend/tests/paper/test_current_analytical_frontier.py` — 0 errors.
  - `git diff --check` — passed.
- **Concerns:** None within T001. T002 must supply the resolved Strategy warm-up count and compose the returned analytical context with Strategy evaluation.
