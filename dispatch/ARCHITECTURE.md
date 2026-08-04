# Feature 06 — Risk Engine Implementation Blueprint

**Status:** Authoritative planning record — developer-approved decisions incorporated
**Date:** 2026-08-04
**Scope:** Feature 06 only; planning only. No application or context files are changed by
this blueprint.

## 1. Purpose and governing principles

The Risk Engine is the single gate between a strategy signal and an order intent. A strategy
proposes direction and may later propose a structural stop; Risk decides whether, how much,
and with which protective levels the proposal may proceed. Strategies must not size orders,
bypass constraints, or implement their own risk limits.

The engine is deterministic, broker-agnostic, Decimal-based, and reusable by paper trading
and backtesting. It owns no database access and does not submit orders.

The approved sizing rule is: **risk per trade is a percentage of current account equity**.
The default is 1% (`0.01`); configuration may not exceed 2% (`0.02`). The engine uses the
configured stop source to derive stop distance and sizes from that distance.

## 2. Agreed vocabulary

- **Signal:** Immutable `backend.strategy.contracts.Signal`, including direction,
  instrument, strategy provenance, candle timestamp, strength, and metadata.
- **Order intent:** The approved, execution-ready consequence of a signal. Feature 06
  represents it with `RiskApproved`; Feature 07 converts it to an order.
- **Entry price:** The intended execution price supplied by the caller in `RiskContext`.
  It is not inferred from `Signal` metadata or fetched by risk.
- **Stop source:** A configuration-selected method: `percentage_of_entry`,
  `absolute_price_distance`, or `explicit_stop_price`.
- **Stop distance:** Absolute price distance from entry to the rounded protective stop used
  for sizing.
- **Net position:** One signed position per account, instrument, and execution mode.
- **Open position:** A position whose status is open/reducing according to the caller's
  snapshot. A pending order is not an open position.
- **Direction conflict:** Any BUY or SELL entry request for an instrument that already has
  a net position, including a request in the same direction. MVP does not scale or reverse.
- **Close signal:** `SignalDirection.CLOSE`; an intent to reduce/close the existing net
  position. It is not a new entry and has zero quantity and zero protective levels.
- **Risk rejection:** A normal, expected business outcome represented by `RiskRejected`.
- **Risk failure:** An unexpected implementation or infrastructure error. It propagates to
  the EventBus failure policy, which records the failure and pauses the bot.

## 3. Boundary and ownership

### 3.1 RiskEngine owns

1. Validating the signal/context relationship for its bot, account, mode, and instrument.
2. Max-open-position control, per-trade equity-risk sizing, stop derivation, optional
   risk/reward take-profit calculation, and instrument constraint validation.
3. Deterministic Decimal arithmetic and conservative rounding.
4. Emitting exactly one `RiskApproved` or `RiskRejected` for each matching entry signal
   evaluated, and approving matching CLOSE signals as zero-quantity intents.
5. Per-bot transient pending-entry reservation/deduplication state.

Every stop—configuration-derived now, and strategy-proposed structure stops in a future
extension—is validated by Risk for direction, positivity, entry geometry, tick rounding,
and sizing safety. No strategy stop can bypass Risk.

### 3.2 RiskEngine does not own

- strategy decisions, ATR calculation, candle loading, account queries, repositories,
  broker calls, order submission, fills, positions, P&L accounting, or persistence;
- fees, slippage, fill timing, protective-trigger candle ambiguity, or reconciliation;
- daily loss, maximum drawdown, session restrictions, cross-bot risk aggregation, leverage,
  or production-mode safety gates.

Feature 07 owns order/fill/position transitions and is the source of truth for durable
position state. Feature 06 receives a context snapshot; it must never query PostgreSQL.

### 3.3 Context-provider boundary and component shape

Implement two layers behind one package boundary:

1. A synchronous, side-effect-free evaluator, `evaluate(signal, context)`, shared by
   backtest and paper mode.
2. An asynchronous EventBus adapter for `SignalGenerated` that filters bot scope, obtains
   a fresh `RiskContext` from the **pipeline-owned context provider**, calls the evaluator,
   and publishes the corresponding event.

The context provider belongs to the bot pipeline/backtester, not RiskEngine. The engine
constructor receives immutable bot identity, `RiskConfig`, EventBus, and a provider
protocol. The engine retains subscription handles and exposes cleanup/unsubscribe behavior.
It must not receive a repository or account service as a disguised query boundary.

## 4. Exact RiskContext contract

The domain contract is a frozen, slotted dataclass. `RiskContext` is caller supplied:

```text
RiskContext
  equity: Decimal
  available_balance: Decimal
  open_positions: tuple[PositionInfo, ...]
  entry_price: Decimal
  instrument: Instrument
  bot_id: UUID
  account_id: UUID
  mode: AccountMode
  clock_timestamp: datetime  # UTC
```

`PositionInfo` is the minimal read-only risk view, not the future Feature 07 Position:

```text
PositionInfo
  account_id: UUID
  bot_id: UUID | None
  instrument_id: UUID
  direction: BUY | SELL
  quantity: Decimal
  status: OPEN | REDUCING
```

There is no mandatory ATR field. There is no mandatory stop field in the context for this
slice: the selected configuration source supplies it. A future structure-stop extension
may add an explicit proposed stop to the signal/context contract, but the resulting stop
still enters the same Risk validation and sizing path.

The context is valid only when its bot/account/mode identity matches the engine and the
signal's instrument matches `instrument.id`. All Decimals must be finite. Equity and
available balance must be non-negative; entry price must be positive; the timestamp must
be UTC. Context validation failures are safe business rejections, not silent skips.

The provider supplies a fresh snapshot for every signal. Backtesting supplies simulation
time and simulated account state; paper trading supplies current paper account state. Risk
does not call `datetime.now()` or a repository.

## 5. Event contracts

Add typed keyword-only payload fields to the existing frozen/slotted events:

```text
RiskApproved(DomainEvent)
  signal: Signal
  position_size: Decimal
  stop_loss: Decimal
  take_profit: Decimal  # Decimal("0") when not configured

RiskRejected(DomainEvent)
  signal: Signal
  reason: str
```

Payload fields are required and immutable. Every emitted event copies `account_id`, `bot_id`,
`mode`, and `correlation_id` from `SignalGenerated`; event IDs are new. A CLOSE approval
has `position_size`, `stop_loss`, and `take_profit` all equal to `Decimal("0")`.

`reason` is a stable human-readable string beginning with a machine-stable code, such as
`invalid_stop`, `missing_stop`, `risk_limit_exceeded`, `direction_conflict`,
`invalid_instrument_constraint`, or `quantity_below_min_notional`. Do not expose stack
traces or secrets. Existing event tests must construct payload fixtures and assert kw-only
fields and metadata preservation.

## 6. Bot filtering and isolation

The process-wide EventBus dispatches signals to all matching handlers, so each engine must:

1. Ignore a foreign `event.bot_id` without context lookup, state mutation, or emitted event.
2. Ignore a missing bot ID because it cannot be attributed to an engine.
3. For a matching bot, reject account, mode, or instrument mismatches with one
   identity-mismatch `RiskRejected`.

Each bot pipeline constructs its own engine, config, provider, reservation set, and
subscription. No mutable risk state or account snapshot is shared between bots. Feature 06
does not maintain bot P&L and must not introduce `_bot_pnl` as a risk source.

## 7. Evaluation order and rejection semantics

For a matching BUY/SELL signal, evaluate in this order:

1. Validate identity, UTC timestamp, Decimal finiteness, positive entry/equity, active
   instrument, risk percentage, stop configuration, and required constraints.
2. Reject an existing same-instrument net position (`direction_conflict`). This covers
   same-direction repetition and opposite-direction reversal.
3. Apply max-open-position limit using open positions plus this engine's pending reservations.
4. Resolve the configured stop source and validate directional stop geometry.
5. Round the stop conservatively to tick size; reject zero/invalid resulting distance.
6. If configured, derive and directionally round take-profit from the risk/reward multiple;
   otherwise emit zero.
7. Calculate quantity from equity, risk percentage, and the rounded stop distance.
8. Floor quantity to `step_size` and validate quantity and notional.
9. Reserve the entry key and publish `RiskApproved`.

Expected rule failures publish one `RiskRejected` and do not raise. Unexpected exceptions
are logged with structured context, re-raised to EventBus, and therefore recorded and pause
the bot; they publish neither decision event nor order intent. Static YAML/configuration
errors fail bot startup through normal validation.

## 8. CLOSE, repeated, and conflicting signals

### CLOSE

`CLOSE` bypasses sizing, stop configuration, max-open-entry counting, and entry constraints.
It is approved with zero quantity and zero SL/TP, preserving provenance and correlation.
Feature 07 may treat a close with no open position as a zero-quantity approved no-op. Risk
does not fabricate a reverse entry.

### Repeated entry signals

An entry is rejected if an open net position exists for the same account, instrument, and
mode, regardless of direction. Before Feature 07 reports a fill, the engine also rejects
the same instrument while its own entry reservation is pending. The reservation key is
`(account_id, instrument_id, mode)` and is released only by an explicit pipeline lifecycle
reset or downstream terminal outcome hook.

### Direction conflicts

BUY while long, SELL while short, and either entry while opposite are all
`direction_conflict`. MVP has no scaling and no automatic reversal: strategies emit CLOSE
first, then a later entry after the position is closed.

## 9. Stop sources, formulas, and rounding

`RiskConfig` selects exactly one stop source for entries:

```text
percentage_of_entry       configured percentage of entry price
absolute_price_distance   configured positive price distance from entry
explicit_stop_price       configured absolute stop price
```

For BUY, percentage and distance sources place the stop below entry; for SELL they place it
above entry. The explicit price must already be on the correct side of entry. A missing,
malformed, non-finite, non-positive, or geometrically invalid stop rejects the signal. A
stop is never guessed, silently defaulted, or replaced by ATR. Strategy-proposed structure
stops are deferred, but when introduced they use the same validation rules.

Let `risk_ratio = Decimal(str(config.per_trade_risk))`, with `0 < risk_ratio <= 0.02` and
default `0.01`. Let `entry` be the context entry price and `raw_stop` the resolved stop:

```text
percentage_of_entry:
  raw_distance = entry * configured_percentage
  BUY raw_stop = entry - raw_distance
  SELL raw_stop = entry + raw_distance

absolute_price_distance:
  BUY raw_stop = entry - configured_distance
  SELL raw_stop = entry + configured_distance

explicit_stop_price:
  raw_stop = configured_stop_price
```

Round the protective stop conservatively to `tick_size`:

```text
BUY  stop = floor(raw_stop / tick_size) * tick_size
SELL stop = ceil(raw_stop / tick_size) * tick_size
```

Then enforce BUY `stop < entry` and SELL `stop > entry`. The sizing distance is
`abs(entry - stop)`, not the pre-rounded distance. Position sizing is:

```text
risk_amount  = equity * risk_ratio
raw_quantity = risk_amount / stop_distance
quantity     = floor(raw_quantity / step_size) * step_size
```

All floor/ceil operations are Decimal integer-multiple operations. No binary float,
implicit precision, or upward quantity rounding is permitted. Zero quantity, invalid
notional, or an instrument violation rejects the signal.

Take-profit is optional. When configured, it uses a configured positive risk/reward multiple
against the actual rounded stop distance:

```text
BUY  take = entry + stop_distance * risk_reward_multiple
SELL take = entry - stop_distance * risk_reward_multiple
```

Round it conservatively away from entry (`ceil` for BUY, `floor` for SELL) and validate its
geometry. There is no hardcoded universal target ratio; omitted take-profit emits zero.

## 10. Instrument constraints

The engine reads provider-aware `Instrument.constraints`, without hardcoding Binance logic.
Required common keys are:

```text
tick_size       required, > 0
step_size       required, > 0
min_qty        optional, default 0
max_qty        optional, default no finite upper bound
min_notional   optional, default 0
```

Missing or malformed required constraints reject safely as
`invalid_instrument_constraint`; they never silently default. Validate
`min_qty <= quantity <= max_qty`, exact step multiple, then
`quantity * entry_price >= min_notional`. OANDA-specific keys remain unsupported until a
later feature and must not be guessed from Binance keys.

`available_balance` remains in the context for the account boundary. Feature 06 validates
that it is non-negative but does not cap risk quantity by balance; affordability belongs to
later execution/account controls.

## 11. Max-open-position state and pending reservations

The authoritative open-position count is the caller's `RiskContext.open_positions`, filtered
to matching account/instrument scope and open/reducing statuses. Count unique net-position
keys, not fills. Pending entry reservations from this engine count toward the configured
per-bot limit and reject duplicate entries.

Pending state is transient only: it is released by explicit pipeline reset and by Feature 07
on terminal order rejection/cancellation. A fill is represented by the caller's next fresh
context snapshot. Restart begins empty after reconciliation supplies authoritative state.
Feature 06 persists no reservations and Feature 07 must not mutate RiskEngine internals.

## 12. YAML/configuration change

Extend `RiskConfig` with `extra="forbid"` and defaults consistent with the approved model:

```yaml
risk:
  per_trade_risk: 0.01
  max_open_positions: 5
  stop_source: percentage_of_entry
  stop_percentage: 0.02
  stop_distance: null
  stop_price: null
  take_profit_risk_reward: null
```

`per_trade_risk` must be finite and satisfy `0 < value <= 0.02`; the default is `0.01`.
`stop_source` is required/validated as one of the three supported values. Its corresponding
value must be present, finite, and positive; irrelevant source values must not be used.
`take_profit_risk_reward` is optional, but when present must be finite and strictly positive.
There is no default take-profit ratio and no ATR multiplier configuration.

Update `config/default.yaml` and configuration tests. Risk remains in bot YAML and supported
UI override paths; do not add a `risk_configurations` table or migration. The exact UI
override mechanism remains outside Feature 06.

## 13. Planned implementation surface

Planning targets only these application/test surfaces; this document itself does not modify
them:

- `backend/core/events.py`: typed RiskApproved/RiskRejected payloads;
- `backend/config.py` and `config/default.yaml`: risk percentage, stop-source, and optional
  risk/reward fields/defaults;
- `backend/risk/engine.py`: context/provider boundary, evaluator, EventBus adapter,
  stop resolution, rounding, constraints, isolation, and lifecycle hooks;
- `backend/risk/errors.py` only if typed validation errors are useful;
- `backend/risk/__init__.py`: public exports;
- `tests/test_events.py`, `tests/test_config.py`, and `tests/test_risk_engine.py`.

No ORM model, repository, migration, broker adapter, execution event payload, or API/UI route
belongs in this slice.

## 14. Test plan

### Contract and event tests

- Payload fields are typed, frozen, keyword-only, and preserve event metadata.
- Approval/rejection correlation and bot/account/mode metadata are copied correctly.
- CLOSE approval contains Decimal zero quantity, SL, and TP; omitted TP on an entry is zero.

### Evaluator math tests

- Default 1% and maximum 2% equity risk are enforced; values above 2% reject.
- All three stop sources resolve correctly for BUY and SELL.
- Missing, invalid, or wrong-side stops reject; no ATR is required or consulted.
- Conservative tick rounding and sizing from the rounded stop distance are correct.
- Percentage, explicit, and distance stop values convert without binary-float arithmetic.
- Quantity floors to step size, never rounds upward, and respects quantity/notional limits.
- Configured risk/reward take-profit rounds away from entry; omitted TP is zero and no
  universal target ratio is assumed.

### Rejection and fail-closed tests

- Bad equity/entry, stop source/value, zero stop distance, and constraints reject safely.
- Max positions rejects at the boundary and includes pending reservations.
- Same-direction repetition and opposite-direction reversal reject.
- CLOSE bypasses entry-only checks and is approved even when already flat.
- Unexpected evaluator/provider exceptions are recorded by EventBus, pause the bot, and emit
  no misleading approval.

### Isolation and integration tests

- Two engines with different bot IDs ignore one another and have independent reservations.
- Foreign events cause no context-provider call and no rejection event.
- Matching signals produce exactly one decision through EventBus.
- Identical backtest and paper contexts produce identical decisions.
- Reservation reset and terminal-outcome hooks behave deterministically.
- The provider is pipeline-owned and no risk path accesses a repository.

The risk engine requires 100% business-logic coverage, plus Ruff, mypy, and the complete
backend test suite. Fixtures use real `Signal`, `Instrument`, UTC timestamps, and Decimals.

## 15. Acceptance gates

Feature 06 is complete only when all are true:

1. Every matching signal receives exactly one approved/rejected decision, except unexpected
   failures following EventBus pause semantics.
2. No foreign bot signal can read or mutate this engine's state.
3. Approved entries use current equity, risk <= 2% (default 1%), a valid configured stop,
   rounded stop distance, Decimal-safe quantity, and all instrument constraints.
4. Optional take-profit is risk/reward-configured; no hardcoded universal target ratio exists.
5. Max-open, pending reservation, repeated-entry, no-scaling, and no-reversal behavior is
   deterministic and tested.
6. CLOSE is explicitly covered as a zero-quantity approved no-op.
7. Risk has no database/repository/broker dependency and the same evaluator serves paper and
   backtest callers through their own context providers.
8. YAML defaults validate, unsafe/missing stop configuration fails closed, and no risk table
   or migration is introduced.
9. Backend tests, Ruff, and mypy pass, with acceptance coverage for every rejection path and
   bot-isolation invariant.

## 16. Explicit non-goals

Deferred: ATR-based stop calculation, mandatory ATR input, strategy-proposed structure stops,
daily loss limits, maximum drawdown halts, session restrictions, cross-bot aggregation,
leverage/margin, balance reservation beyond transient duplicate protection, scaling,
close-and-reverse, hedging, multiple positions, dynamic trailing stops, broker-specific API
rules, order types other than the downstream MVP market-order contract, fees/slippage,
persistence, API/UI configuration endpoints, and production trading safety.

Risk does not calculate indicators, simulate fills, decide next-candle timing, or own
protective exit triggering. These concerns remain outside Feature 06 to preserve the shared,
deterministic backtest/paper contract.

## 17. Feature 07 handoff

Feature 07 may subscribe to `RiskApproved` and must treat it as the only eligible entry
intent. It preserves signal, position size, stop loss, optional take profit, and account/bot/
mode/correlation identity when creating an order. A zero-quantity CLOSE is an approved close
intent and may become an execution no-op when no position exists; it is not a reversal order.

Feature 07 owns market-order translation, client-order idempotency, fill/position/trade state,
durable persistence, fees/slippage, paper fill timing, protective-trigger rules, and
reconciliation. It supplies context snapshots that reflect fills/open positions and releases
pending reservations only through the defined terminal rejection/cancellation lifecycle hook.
It must never bypass Risk or mutate RiskEngine internals. Unknown broker state remains
fail-closed and is resolved by reconciliation, not risk retries.

## 18. Authoritative approved decisions

The following decisions are final for Feature 06 and supersede the former ATR-based draft:

1. Risk is at most 2% of current account equity per trade; default is 1%.
2. Stops are configuration-driven from percentage of entry, absolute price distance, or
   explicit stop price. Missing/invalid stops reject.
3. Strategy-proposed structure stops are future work and always pass through Risk validation.
4. Size is `equity * risk percentage / rounded stop distance`, with Decimal-safe rounding and
   instrument constraints.
5. MVP has no scaling or automatic reversal. CLOSE is a zero-quantity approved no-op.
6. Take-profit is optional and, when configured, uses a configured risk/reward multiple; no
   universal target ratio is hardcoded.
7. The pipeline/backtester owns context acquisition; Risk is a pure evaluator plus adapter.
8. Pending reservations are transient, per-bot, and released only through lifecycle/reset
   hooks; failures follow EventBus recording and bot-pause semantics.

**This blueprint is authoritative for Feature 06 implementation planning.**
