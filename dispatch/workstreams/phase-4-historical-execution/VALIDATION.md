# VALIDATION — Phase 4 Historical Execution (Task 07 re-validation)

**Result: PASS — independent Task 07 re-validation succeeded; re-review may proceed.**

The two Important review findings (Finding A: slippage not wired + sizing order;
Finding B: end-close coverage + final-equity timing) are remediated and covered by
permanent end-to-end tests. Nonzero adverse slippage is applied to the executable
side *before* PRE_SUBMISSION sizing; Risk enforces `actual_risk <= risk_budget` with
entry/target/fill economics and persisted provenance in agreement; the zero-slippage
path is covered; the END_OF_EXPERIMENT exit is atomic (Fill + Trade close + Position
flatten + sibling protection cancellation) and the terminal equity point reconciles
to the result `ending_equity`. The full suite and practical gate pass. Findings C/D
remain Minor follow-ups and were not expanded into this task.

- **Workstream:** `dispatch/workstreams/phase-4-historical-execution/`
- **Validator role:** tester (independent, Task 07 re-validation)
- **Branch / SHA (working tree):** `feature/phase-4-historical-execution`; Task 07
  changes are working-tree only (no commit), matching `TASK-07-review-remediation.md`.
- **Environment:** macOS, Python 3.13, PostgreSQL 18.4 (local `atlas_test`),
  `ATLAS_TEST_DATABASE_URL` configured.

## Scope of this validation

Independently revalidate only the approved Task 07 remediation: (1) wire configured
nonzero adverse slippage end-to-end with slippage applied before Risk sizing and
agreement across target/fill/provenance, plus the zero-slippage path; (2) reconcile
END_OF_EXPERIMENT terminal accounting (atomic close, protection cancellation, final
equity = result equity); (3) reassess the two Minor review observations without scope
expansion. I own and wrote only this artifact. I did not modify application code,
repo tests, context, dispatch artifacts, or Git state. All verification was read-only
plus test execution.

## Method

1. Read governing inputs: `AGENTS.md`, `dispatch/ACTIVE.md`, workstream `PLAN.md`,
   `ARCHITECTURE.md`, `REVIEW.md` (findings A–D), the TASK-07 receipt, and the prior
   `VALIDATION.md` (Task 06 PASS, reused as the base that passed re-review).
2. Used CodeGraph guidance then read the full on-disk source of `runner.py`,
   `simulated.py`, `fill_application.py`, `risk/service.py`, and the Task 07 test
   additions in `test_golden_flows.py`.
3. Ran the practical gate: full suite, focused Task 07 suite, ruff, compileall,
   migration head check, and a forbidden-import boundary scan.

## Commands and results (recorded)

| Command | Result |
| --- | --- |
| `uv run pytest backend/tests/integration/test_golden_flows.py -q -k phase4` | **6 passed** (4 parametrized slippage reproducibility + FAILED-no-result + END_OF_EXPERIMENT atomic/equity-reconcile) |
| `uv run pytest -q` (full suite incl. integration) | **180 passed, 1 skipped** in 133.1s, 1 existing dependency warning (httpx2/Starlette) |
| `uv run ruff check` over all 9 changed non-test Phase 4 modules + 5 test files | **All checks passed** |
| `python -m compileall -q backend/experiments backend/execution backend/persistence` | passed |
| `uv run alembic heads` | head `0006_phase_4_persistence` |
| Forbidden-import scan over 8 changed non-test modules + migration (api/ui/runtime/broker/paper/live/scheduler/worker/redis/httpx) | no forbidden imports |
| `git status --short` | only pre-existing Task 07 changed paths + workstream + `.codegraph/`; no new changes from this validation |

## Independent source review — Finding A (slippage wired; sizing order)

Confirmed in `backend/experiments/runner.py`:

- `_run_phase4` reads `simulation_config["slippage_model"]` and, when no execution
  adapter was explicitly supplied, builds
  `SimulatedExecutionAdapter(slippage_ticks=slippage["ticks"], tick_size=…)`
  (`runner.py:267–272`). Default Phase 4 execution is therefore config-driven.
- `_attempt_entry` builds a `slipped_quote` applying adverse slippage to the
  executable side **before** `evaluate_pre_submission` (`runner.py:413–417`):
  LONG uses `ask_open + slippage`, SHORT uses `bid_open - slippage`; the raw
  BID/ASK is retained as executable provenance.
- `RiskService.evaluate_pre_submission` sizes from that slipped entry
  (`risk/service.py:122–148`): `entry` = slipped ask/bid, stop geometry validated
  against it, `loss_per_unit = |entry − stop|`, `quantity = floor(budget/loss_per_unit)`,
  and **`actual_risk > budget` → `INVALID_QUANTITY` rejection** (`service.py:140–141`),
  so approved risk always satisfies `actual_risk <= budget`. Target resolves from the
  slipped entry (`intent.target.resolve(entry, stop, direction)`).
- Fill economics match sizing: the adapter applies the identical adverse slippage to
  an ENTRY fill (`simulated.py:148–153`), so `execution_price` equals the risk
  `entry_price`; Fills persist raw `executable_reference_price`, `slippage_per_unit`,
  and `slippage_cost` (`simulated.py:181–193`).

The permanent parametrized test
`test_phase4_remediation_is_reproducible_and_records_starting_equity`
(`LONG`/`SHORT` × `slippage_ticks` 0 and 2) asserts `first_risk.entry_price ==
first_fill.execution_price`, `actual_risk == quantity * |entry − stop|`, and for
nonzero ticks `execution_price == raw ± 0.00002` (2 ticks × `0.00001`), plus fresh-ID
byte-identical `_semantic_payload` and `output_fingerprint`. **Verified PASS.**

## Independent source review — Finding A zero path

With `slippage_ticks = 0`, `self.execution.slippage = 0` (`simulated.py:53`), so the
slipped quote equals the raw quote and the fill price equals the raw executable open
with `slippage_per_unit`/`slippage_cost` zero (`simulated.py:181`). Both `LONG` and
`SHORT` zero-slippage cases are exercised in the same parametrized test. **Verified PASS.**

## Independent source review — Finding B (END_OF_EXPERIMENT)

Confirmed in `runner.py` and `fill_application.py`:

- The loop defers the final equity sample while exposed (`runner.py:325–329`), so no
  pre-exit (open/unrealized) point is persisted at the terminal `end_time`. After the
  loop, `_close_at_end` (`runner.py:334,478–489`) creates a MARKET `EXIT` order,
  executes an adverse-slipped close at the final eligible side close, and applies the
  Fill; then `_sample_equity` records the terminal point (`runner.py:335`).
- `apply_fill` for an EXIT purpose closes the Trade with `exit_reason =
  END_OF_EXPERIMENT`, flattens the Position, updates `realized_pnl`, deducts the exit
  commission, and atomically cancels both protection siblings
  (`fill_application.py:181–228`, `_cancel_protection_siblings` at `:57–71,228`).
- The post-close equity point is FLAT (`unrealized = 0`, `equity = starting_capital +
  realized_pnl`), so it equals `account.equity`; `_complete_phase4` persists
  `ending_equity`/`ending_balance` from the same account state (`runner.py:515–527`).

`test_phase4_end_close_is_atomic_and_terminal_equity_reconciles` suppresses protection
fills (forcing the end-open path) and asserts: Position FLAT; Trade `COMPLETED` with
`exit_reason = END_OF_EXPERIMENT`; last Fill `price_basis = END_CLOSE`; EXIT order
`FILLED` and STOP_LOSS/TAKE_PROFIT both `CANCELED`; `equity[-1].observed_at ==
trading_end`; `equity[-1].equity == result_row.ending_equity == ending_balance`; and
`commission_cost == 0.10 * 2 * quantity` (entry + exit). **Verified PASS.**

## Minor review observations reassessed (no scope expansion)

- **Finding C (Minor)** — `_run_phase4` still does not explicitly validate the
  snapshot `integrity_summary` status nor coverage-vs-`trading_end` bounds
  (`runner.py:262–290`). This is unchanged by Task 07 and is documented as a follow-up
  finding in the TASK-07 receipt.
- **Finding D (Minor)** — decision frontiers are still keyed by
  `observation.start_time` (`runner.py:289,307`), so a session-closed decision
  frontier is not evaluated, and mid-stream gap detection is unchanged (`clock.py`).
  Unchanged by Task 07 and documented as a follow-up finding.

Both remain Minor and were explicitly **not broadened** into Task 07, consistent with
the receipt. Neither blocks this re-validation of the two Important remediations, and
no scope expansion was introduced.

## Reused / not-reused receipts

- **Reused (valid, re-verified):** prior `VALIDATION.md` PASS (Task 06 base that
  passed re-review) and the TASK-01..06 receipts remain valid for the paths they cover;
  the Task 06 changes are untouched by Task 07.
- **Not reused:** none of the Task 07 focused or full-suite results were assumed — all
  were re-run here.

## Pass / fail decision

**PASS.** Finding A is remediated and covered end-to-end: configured adverse slippage
is applied before Risk sizing, `actual_risk <= budget` is enforced, and entry/target/
fill/provenance agree (zero and nonzero paths). Finding B is remediated and covered:
the END_OF_EXPERIMENT close is atomic with sibling cancellation and the terminal equity
point reconciles exactly to the result `ending_equity`. The full suite and practical
gate pass. Findings C/D remain Minor follow-ups, not addressed here and not blocking.
Re-validation is complete; re-review may proceed.

## Required next gate

Dispatch review per `ACTIVE.md` (`REVIEW.md` owned by reviewer), gated on this passing
Task 07 re-validation.
