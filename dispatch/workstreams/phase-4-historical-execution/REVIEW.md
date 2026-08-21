# REVIEW — Phase 4 Historical Execution

Gate: **R1** (formal review; feature work)
Spec compliance: **PASS**
Task quality: **PASS**
Layer 1 (plan alignment): **PASS**
Layer 2 (system integrity): **PASS**
Layer 3 (production readiness): **PASS**
Findings: **0 Important — Findings A & B resolved and covered by permanent end-to-end tests; 2 Minor follow-ups remain (C, D), accepted and documented**
Evidence reused: VALIDATION.md Task 07 re-validation (PASS, full suite 180 passed/1 skipped, focused phase4 6 passed, ruff, compileall, alembic head, forbidden-import scan); TASK-01..06 receipts (paths they cover)
Checks rerun: `pytest test_golden_flows.py -k "phase4_remediation or phase4_end_close"` — 5 passed (4 parametrized slippage reproducibility + end-close atomic/equity reconcile) — reason: focused re-verification of the two previously-blocking findings on the current working tree; `ruff check runner.py test_golden_flows.py` — passed; `alembic heads` — 0006 head; forbidden-import scan — clean
Decision: **PASS**

---

## Re-review (post Task 07)

Re-reviewed the current working tree (branch `feature/phase-4-historical-execution`, no
commit; Task 07 changes working-tree only, matching `TASK-07-review-remediation.md` and
`VALIDATION.md`). The prior gate was **BLOCKED** on two Important findings (A: slippage
not wired + sizing order; B: end-close coverage + final-equity timing). Both are verified
resolved below.

### Finding A — resolved

`runner.py:267-272` reads `simulation_config["slippage_model"]` and builds
`SimulatedExecutionAdapter(slippage_ticks=…, tick_size=…)` from config (unless an
adapter was explicitly supplied for deterministic test control). `runner.py:413-417`
builds a `slipped_quote` applying adverse slippage to the executable side *before*
`evaluate_pre_submission` (LONG ask+slippage, SHORT bid−slippage), so Risk sizes from the
slippage-adjusted actual entry; `risk/service.py:122-141` derives entry/stop geometry/
quantity/target/`actual_risk` from that slipped entry and rejects
`actual_risk > budget` (`INVALID_QUANTITY`) — fail-closed sizing. The adapter applies the
identical adverse slippage on ENTRY fills (`simulated.py:148-153`), so `entry_price` ==
`execution_price`. Raw BID/ASK is retained as executable provenance
(`_persist_risk` at `runner.py:418`). `_validate_phase4_config` now validates the full
mandated config (schema, execution, slippage model/ticks/tick_size, commission,
financing disclosure, intrabar policy, target policy, end policy, equity sampling, risk
config). Zero and nonzero slippage, both directions, are covered by the permanent
parametrized `test_phase4_remediation_is_reproducible_and_records_starting_equity`
(asserts `entry_price == execution_price`, `actual_risk == quantity*|entry−stop|`, and
for nonzero ticks `execution_price == raw ± 0.00002`, plus fresh-ID fingerprint
equality).

### Finding B — resolved

The loop defers the terminal equity sample while the Position is still open
(`runner.py:325-329`), so no pre-exit unrealized point is persisted at the terminal
`end_time`. After the loop, `_close_at_end` (`runner.py:478-489`) creates a MARKET EXIT
order, executes the adverse-slipped close at the final eligible side close, and applies
the Fill; only then `_sample_equity` records the realized (FLAT) terminal point
(`runner.py:330-335`). `apply_fill` EXIT closes the Trade (`exit_reason=END_OF_EXPERIMENT`),
flattens the Position, deducts exit commission, and atomically cancels both protection
siblings (`fill_application.py`). The permanent `test_phase4_end_close_is_atomic_and_terminal_equity_reconciles`
suppresses protection (forcing the end-open path) and asserts: Position FLAT; Trade
COMPLETED/END_OF_EXPERIMENT; last Fill `price_basis=END_CLOSE`; EXIT FILLED and
STOP_LOSS/TAKE_PROFIT CANCELED; `equity[-1].observed_at == trading_end`;
`equity[-1].equity == result_row.ending_equity == ending_balance`; and
`commission_cost == 0.10 * 2 * quantity` (entry + exit).

### Minor findings (C, D)

Unchanged and explicitly **not** broadened into Task 07 (per receipt and VALIDATION):
C (snapshot integrity/coverage-bounds validation not explicitly checked) and D
(session-closed decision frontiers / mid-stream gap detection). Both are accepted
follow-up findings, non-blocking.

### Scope integrity

`git diff --stat HEAD` is limited to the Phase 4 application/migration/test files plus
dispatch artifacts (runner, execution/contract, execution/simulated, execution/
fill_application, experiments/clock, persistence models/repositories, migration
`0006_phase_4_persistence_contract`, and the Phase 4 tests). Alembic head is
`0006_phase_4_persistence`. No forbidden imports (api/ui/runtime/broker/redis/httpx/
scheduler/worker) across the changed non-test modules. No Phase 5, PAPER/LIVE, broker,
API, or UI scope introduced.

## Basis

Reviewed against `AGENTS.md`, `dispatch/ACTIVE.md`, `PLAN.md`, `EXPLORATION.md`,
`ARCHITECTURE.md`, `READY.md`, `TASK-01..06`, `VALIDATION.md`, and the on-disk source
of the changed Phase 4 modules: `backend/experiments/runner.py`,
`backend/experiments/clock.py`, `backend/execution/contract.py`,
`backend/execution/simulated.py`, `backend/execution/fill_application.py`,
`backend/persistence/models.py`, `backend/persistence/experiment_repository.py`,
`backend/persistence/trading_repository.py`,
`backend/persistence/migrations/versions/0006_phase_4_persistence_contract.py`, the
market-data/risk/strategy boundary modules, and the integration/unit tests. Used
CodeGraph first. No Git operations performed.

Verified state: branch `feature/phase-4-historical-execution` @ `5188b194ce9b3e5a688296051267aad98a9d3fa2`
matches `READY.md` and `VALIDATION.md`; Phase 4 changes are working-tree only; scope
is limited to the Phase 4 application/migration/test files plus dispatch artifacts.

## Layer 1 — Plan alignment

Confirmed present and correct:

- **Frontier / no-lookahead.** `SimulationClock.observations()` yields chronological
  complete M1 BID/ASK/MID observations over `[trading_start, trading_end)`; `frames()`
  keeps warm-up (exposure_allowed=False), decision, and end semantics; M15 derivation
  reuses the single existing `aggregate_m1_to_m15` boundary. A decision at frontier `T`
  is evaluated only when the observation with `start_time == T` is processed; entry uses
  that observation's open, so signal-bar data is never reused for execution. The same
  M15 bar is evaluated at most once (decisions dict keyed by frontier, unique observation
  minutes). Warm-up never allows exposure.
- **Fill authority / accounting.** `apply_fill` is the sole persistence boundary that
  changes exposure/accounting; Order creation/submission never mutates Position/Trade/
  account. One Position, sequence-numbered Trades, `max(sequence)+1` allocation, atomic
  Fill + OrderEvent + Position + Trade + account/cost update under a nested savepoint,
  terminal protection-sibling cancellation, commission as Fill fee, financing stays
  `NULL` with `FINANCING EXCLUDED` disclosure. Entry/stop/exit adverse-side fills and
  target-at-requested-price (no slippage/improvement) match the blueprint.
- **Protection & ambiguity.** STOP_LOSS wins an unknowable dual touch; `STOP_LOSS_ADVERSE_FIRST_V1`
  policy and ambiguity facts recorded on the affected Trade. Same-bar entry+protection
  only after the entry Fill; no pyramiding/no reversal enforced by Risk rejecting
  non-FLAT entries (persisted rejection, loop continues).
- **Multi-Trade & reproducibility.** Two sequential long/short Trades demonstrated; all
  Phase 4 Orders link deterministically to the returned PRE_SUBMISSION row (fix for
  prior finding 1); `initial_risk` stable; `_semantic_payload` covers risk phase/
  actual_risk and Trade initial_risk; `trading_start` equity point exact; fresh-ID
  semantic equality and matching output fingerprints asserted.
- **Immutable persistence / migration.** Forward `0006_phase_4_persistence` after
  `0005`; additive nullable columns for legacy rows, required-only for
  `PHASE4_HISTORICAL_EXECUTION_V1`; append-only and terminal-graph triggers; parent
  protection guard keyed on model version so the Phase 3 runner remains compatible;
  results one-to-one; no fabricated/backfilled Phase 3 values; downgrade removes only
  Phase 4 schema. Phase 3 path preserved in `run()`/`_open_and_close`.
- **Exclusions honored.** No PAPER/LIVE, broker, API, UI, `atlas-runtime`, scheduler,
  optimization, or new historical trading nouns; changed modules import no
  api/ui/runtime/broker infra (forbidden-import scan in VALIDATION).

### Finding A — Important — configured slippage is not wired; sizing order contradicts the blueprint

**Location:** `backend/experiments/runner.py:175` (default `SimulatedExecutionAdapter()`),
`:365–373` (PRE_SUBMISSION sizes from raw quote), `:339–348` (`_validate_phase4_config`
validates only `schema_version` and `commission_model`); `ARCHITECTURE.md` invariant 6,
decision table, `simulation_config` list, acceptance matrix ("explicit zero and nonzero
adverse slippage").

**Evidence:** The blueprint mandates `simulation_config.slippage_model` as part of the
immutable config and invariant 6: "Apply adverse slippage to the relevant executable
side before sizing. If stop geometry becomes invalid, persist rejection and continue."
Decision table: "PRE_SUBMISSION sizes from the slippage-adjusted actual entry, and the
target resolves from that entry." In the implementation:
- `_run_phase4`/`ExperimentRunner.__init__` construct `SimulatedExecutionAdapter()`
  with the default `slippage_ticks=0` and never read `slippage_model` from
  `experiment.simulation_config` (grep across `backend/` finds `slippage_model` nowhere).
- `evaluate_pre_submission` is given the raw `obs.bid_open/ask_open` quote; quantity,
  stop geometry, target, and `actual_risk` are all derived from the **un-slipped** entry
  price. Adverse slippage is applied only later, at Fill time in the adapter.
- `_validate_phase4_config` does not validate `slippage_model` (nor `financing_model`,
  `spread_model`, `intrabar_policy`, `end_policy`, `equity_sampling`,
  `target_fill_policy`, all absent from the codebase).
- Nonzero slippage exists only in the pure-adapter unit tests
  (`test_simulated.py`); it is never exercised through the runner/persistence. The
  acceptance requirement "explicit zero and nonzero adverse slippage" is therefore not
  proven end-to-end, and a configured nonzero slippage model would be silently ignored
  while the persisted `simulation_config` claims it was applied.

**Impact:** The modeled execution does not honor the approved slippage model: risk sizing,
target, actual risk, and actual_risk/provenance do not reflect the "slippage-adjusted
actual entry" the blueprint requires. When slippage > 0, realized risk exceeds the
reported `actual_risk`/`initial_risk`, understating risk per the fail-closed principle.
The current fixtures (zero slippage) mask the defect.

**Remedy:** Wire `simulation_config.slippage_model` into the runner's adapter (construct
`SimulatedExecutionAdapter(slippage_ticks=…, tick_size=…)` from config) and validate the
full mandated config before any trading fact is written. Apply adverse slippage to the
executable side *before* calling `evaluate_pre_submission` (so entry, stop geometry,
quantity, target, and actual_risk derive from the slipped entry). Add an end-to-end
nonzero-slippage integration test asserting slipped entry/target/actual_risk and the
fingerprint reflects it.

### Finding B — Important — end-of-experiment path has no end-to-end coverage and the final equity point precedes the end close

**Location:** `runner.py:315–321` (in-loop `_sample_equity` then `_close_at_end` then a
deduped second sample), `:439–461` (`_sample_equity` dedup at `:459–460`); no test
exercises `_close_at_end`.

**Evidence:** `_sample_equity` records a point at each observation's `end_time` while the
Position is still open (unrealized). If the Position is open at the last observation,
`_close_at_end` closes it at that same close, then the second `_sample_equity` call for
the same `end_time` is discarded by the dedup guard (`if previous is not None and
previous.observed_at == when: return`). The equity curve's terminal point therefore
reflects the pre-exit (open, unrealized) state, while the result's `ending_equity` uses
`account.equity` post-exit (realized, exit commission deducted). They differ by the exit
fill's cost/slippage. This exact "open Position at end" case (acceptance matrix "End
handling") is not covered by any integration test: the golden-flow Phase 4 tests close via
protection mid-run and the failure test fails early; the only `END_CLOSE`/`END_OF_EXPERIMENT`
coverage is the pure adapter (`test_simulated.py`).

**Impact:** A required acceptance area is untested end-to-end, and the equity curve can be
internally inconsistent with the authoritative result `ending_equity` (final equity point
≠ ending_equity) for the end-open case, which also skews the persisted max-drawdown basis.

**Remedy:** Add an integration test that leaves a Position open at `trading_end` and
asserts the `END_OF_EXPERIMENT` exit at the final eligible side close, sibling
cancellation, and that the final equity point reconciles to the result `ending_equity`
(either sample post-exit, or make the end-close ordering explicit and consistent with
blueprint invariant 13).

## Layer 2 — System integrity

Boundaries are preserved: Strategy/Risk/execution/persistence ownership unchanged; Fill
is the sole financial transition; one Position projection reused across Trades; no broker
or Phase 5 infrastructure introduced. The migration guards, immutability triggers, and
Phase 3 compatibility were reviewed and are internally consistent (result insert before
`mark_completed` so the append-only guard is satisfied; failure fields carved out of the
config-immutability check so `mark_failed` proceeds). **PASS.**

## Layer 3 — Production readiness

Tests/validation are strong for the covered scope (deterministic fixtures, fresh-ID
semantic equality, ambiguity, multi-Trade, FAILED-no-result, migration cycle, ruff,
compileall). Gaps: nonzero slippage not wired/covered (Finding A); end-open path
uncovered with a final-equity timing inconsistency (Finding B). Two Minor items below.

### Finding C — Minor — requested-period coverage / dataset integrity not explicitly validated

`_run_phase4` (`runner.py:262–280`) validates config and warms up, but does not verify
that the DatasetSnapshot has `integrity_summary` status VALID, nor that it covers
warm-up + the requested `[trading_start, trading_end)`. A `trading_end` beyond coverage
would silently run a truncated stream and close at the last available quote rather than
failing as blueprint invariant 1 requires. Remedy: validate snapshot integrity and
coverage bounds before any trading fact is written.

### Finding D — Minor — session-closed decision frontiers are skipped; mid-stream gap detection is incomplete

`runner.py:299–300` keys decisions by `observation.start_time`; a DECISION frontier that
falls on a session-closed minute has no observation, so its M15 bar is never evaluated
(Strategy state does not advance on it). `clock.py:199–216` yields only minutes present in
data, so an unexpected open-session minute gap mid-stream is silently skipped rather than
failing (only decision frontiers check for a missing completed M1). Conservative (no
exposure at closed minutes) but a deviation from "evaluate each completed frontier" and
"unexpected gaps fail". Remedy: evaluate every DECISION frontier (state advance) and add
gap detection across the full execution stream.

## Evidence reused and reruns

- **Reused (valid, Task 07 scope applies):** `VALIDATION.md` Task 07 re-validation PASS
  (full suite 180 passed/1 skipped, focused phase4 6 passed, ruff, compileall, migration
  head `0006_phase_4_persistence`, forbidden-import scan); `TASK-01..06` receipts for the
  paths they cover (unchanged by Task 07).
- **Rerun on current working tree:** focused `test_golden_flows.py` selection covering the
  two previously-blocking findings (`-k "phase4_remediation or phase4_end_close"`) — 5
  passed; `ruff check` on the two Task 07 files — passed; `alembic heads` — 0006 head;
  forbidden-import scan — clean. Reason for rerun: re-verify the remediated Finding A and
  B paths directly rather than relying solely on the receipt, given the re-review gate.

## Decision

**PASS.**

Both previously-blocking Important findings are remediated and covered by permanent
end-to-end tests, verified by independent source inspection plus a focused test rerun:
Finding A (configured adverse slippage applied to the executable side before Risk sizing,
with entry/target/fill/provenance agreement and `actual_risk <= budget` enforcement, zero
and nonzero paths) and Finding B (END_OF_EXPERIMENT atomic close with sibling
cancellation and the terminal equity point reconciling exactly to the result
`ending_equity`). Scope is intact, migration head is correct, and no forbidden imports
were introduced. Minor findings C and D remain as documented, accepted follow-ups and do
not block closure.
