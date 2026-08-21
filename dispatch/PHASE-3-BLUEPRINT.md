# Implementation Blueprint — Atlas Phase 3: First Historical Trade

**Blueprint ready.** Builders must follow this contract and return material conflicts to the orchestrator.

## Outcome and boundary

Build two persisted, deterministic historical Experiments—one LONG and one SHORT—each proving exactly one `FLAT → exposed → FLAT` episode:

`completed M15 Bar → StrategyDecision → TradeIntent → RiskDecision → Order → Fill → Position → Trade`

Included: immutable Experiment provenance, SimulationClock, SimulatedAccount (never TradingAccount), canonical TradeIntent/RiskDecision/Order/Fill/Position/Trade, PRE_FLIGHT/PRE_SUBMISSION Risk, whole-unit EUR/USD sizing, snapshot-only inputs, simulated full Fills, PostgreSQL persistence, and inspectable sanitized failures.

Excluded: API/UI/CLI/runtime/OANDA/PAPER/LIVE/reconciliation; full M1 replay, intrabar ordering/adverse-first behavior, gaps/slippage/costs/equity history/metrics/forced end close/multiple Trades; partial Fills, protective Order lifecycle, daily loss/drawdown/margin, and generalized infrastructure.

Persist and disclose model `PHASE3_OPEN_CHECKPOINT_V1`; it is not Phase 4 execution realism. A run ends after its first completed Trade. No completed Trade is `PHASE3_TRADE_NOT_COMPLETED`, never success.

## Fixed semantics

- Rename the existing Strategy-state `Position` enum to `PositionState`; add a separate canonical financial Position.
- At UTC frontier `T`: (1) complete M1 ending `T` only to detect unsupported intrabar touches; (2) evaluate the completed MID M15 ending `T` exactly once; (3) expose only BID/ASK opens for M1 starting `T`. A decision at `T` cannot use earlier prices or the new M1 high/low/close.
- Read only immutable DatasetSnapshot membership (EUR/USD/OANDA M1 MID/BID/ASK), derive M15 via existing snapshot-only code, and resolve StrategyVersions only through the verified registry. Never use mutable current bars.
- Use UTC/M15-aligned `[trading_start,trading_end)`. Warm up completed bars ending at/before start with exposure disabled; require StrategyVersion warmup (currently 100). Trade only when `trading_start < bar.end_time < trading_end`.
- PRE_FLIGHT requires RUNNING Experiment, actionable direction, known FLAT Position, known positive-equity account, valid config/stop/target. PRE_SUBMISSION repeats checks at executable quote: long ASK with `stop < entry`; short BID with `stop > entry`; budget is equity × risk rate; floor budget/loss-per-unit to whole units; reject invalid/below-one quantity and assert actual risk ≤ budget.
- Required Risk rejections: `POSITION_ALREADY_OPEN`, `INVALID_STOP`, `INVALID_QUANTITY`, `ACCOUNT_STATE_UNKNOWN`, `EXPERIMENT_NOT_RUNNING`, `UNSUPPORTED_INSTRUMENT_ECONOMICS`.
- Resolve target from actual entry: long `entry + multiple × (entry-stop)`; short `entry - multiple × (stop-entry)`. Long liquidation is BID; short liquidation is ASK. Target-at/open fills at target; exact stop-at/open fills at stop; beyond-stop gap fails `UNSUPPORTED_PHASE3_STOP_GAP`; any unsupported intrabar touch fails `UNSUPPORTED_PHASE3_INTRABAR_TRIGGER`.
- SimulatedExecutionAdapter is pure: canonical Order + reduced observation → one full Fill, with no persistence/state mutation. Entry is MARKET/ENTRY; supported exit is LIMIT/TAKE_PROFIT or STOP/STOP_LOSS.
- One atomic Fill application boundary updates `Fill → Order → Position → Trade → SimulatedAccount`. Only Fill changes exposure. Decimal/NUMERIC only; long P&L `(exit-entry)×quantity`, short `(entry-exit)×quantity`; no fees/costs.

## Persistence and modules

Add Alembic `0004_phase_3_first_historical_trade` after Phase 2, using the existing declarative base. Add only `experiments`, `experiment_accounts`, `trade_intents`, `risk_decisions`, `orders`, `fills`, `positions`, and `trades`. Enforce restrictive FKs, UTC timestamps, positive financial checks, immutable facts/configuration, terminal projection guards, and unique Position/intent-frontier/Risk-phase/Fill-sequence constraints. No TradingAccount, Deployment, RiskProfile, OrderEvent, equity-history, or SystemEvent tables.

Create focused Experiment/Trading repositories (caller-owned Session); extend DatasetSnapshotRepository only for ordered membership-bounded M1 reads/source IDs. Recommended modules: `domain/experiment.py`, `domain/trading.py`, `risk/service.py`, `execution/{contract,simulated,fill_application}.py`, and `experiments/{clock,runner}.py`.

Failures are categorized VALIDATION, MARKET_DATA, STRATEGY, RISK, EXECUTION, or PERSISTENCE, stop new exposure, preserve any open Position without invented closure, and contain only sanitized detail. No credentials/network behavior or arbitrary-object deserialization is introduced.

## Ordered work
1. Establish a new dedicated current-checkout feature branch and READY receipt after separate exact-command confirmation.
2. Rename `PositionState`; add strict domain contracts/tests.
3. Add migration/models/protections; prove migration cycle and constraints.
4. Add snapshot-bounded M1 reads; prove current mutable bars cannot enter a run.
5. Add repositories and atomic Fill state transition.
6. Implement central Risk with sizing/rejection tests.
7. Implement execution adapter; prove Order creation cannot alter exposure.
8. Implement clock ordering/no-lookahead checks.
9. Implement runner: warmup, facts, entry, target, supported closure, and fail-closed handling.
10. Build real EMA Strategy + real persisted snapshot LONG/SHORT golden fixtures; no stubbed decisions.
11. Document model exclusions; run quality, migration, unit, integration, full-suite, and scope review gates.

## Completion evidence

For both golden flows, persisted facts must prove source StrategyVersion/DatasetSnapshot/model, M15 decision frontier, immutable intent, approved Risk phases, post-decision quote, correct entry/exit sides, source M1 identities, target from actual entry, closed Trade/P&L/R, updated account, FLAT Position, and COMPLETED Experiment. Equivalent reruns must match semantic results excluding generated IDs/timestamps. Review must prove no signal-bar execution reuse, Strategy never sized/submitted, Risk alone sized, Fill alone changed exposure, and no Phase 4 behavior was silently applied.

**Confirmed/high:** roadmap governs; Strategy purity, snapshot immutability, Fill authority, SimulatedAccount, no pyramiding, and BID/ASK economics. **Assumed/high:** separate long/short acceptance runs and fail-closed unsupported Phase 4 conditions. **Deferred/high:** full execution realism, costs/equity/end handling, partial/broker behavior, PAPER/OANDA/reconciliation. Schema rollback is destructive and requires explicit approval; preserve facts and roll forward after use.

Implementation requires explicit developer approval of this blueprint and workflow. Approval does not authorize Git operations.
