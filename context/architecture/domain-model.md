# Domain Model

## Purpose

This document defines the canonical Atlas domain language. If multiple files use the same concept, this document owns its meaning unless a more specific feature specification defines behavior for that concept. Do not introduce parallel nouns for existing concepts.

## Core Lifecycle

Strategy → StrategyVersion → Experiment or Deployment → TradeIntent → RiskDecision → Order → Fill → Position → Trade. Supporting: Instrument, VenueInstrument, DatasetSnapshot, TradingAccount, RiskProfile, OrderEvent, SystemEvent.

## Strategy

A Strategy is the long-lived identity of a trading methodology (currently EMA
Sweep Confirmation Break). It does not itself represent one immutable executable
version — that belongs to StrategyVersion. The current executable version is v2.

## StrategyVersion

An immutable executable snapshot of a Strategy. Preserves enough provenance to identify the methodology used by Experiments, PAPER Deployments, LIVE Deployments. A new StrategyVersion is required when executable behavior changes. Parameter value changes do not create a new StrategyVersion. See: [Strategy Contract](strategy-contract.md).

## Instrument

Atlas's canonical identity for a tradable market (e.g., EUR/USD). Independent of broker/provider naming.

## VenueInstrument

Maps an Atlas Instrument to a specific broker/provider representation and venue-specific rules. E.g., Instrument EUR/USD + Venue OANDA → EUR_USD. Venue-specific symbols must not become canonical Atlas Instrument identity.

## DatasetSnapshot

Identifies the immutable historical market-data view used by an Experiment.
Preserves provenance for the independent native products: OANDA M15 MID for
analysis and sparse M1 BID/ASK for execution, including resolution, components,
coverage, alignment, fingerprint, and integrity metadata. M1 does not substitute
for missing native M15. Does not require physically copying all bars for every
Experiment.

## Experiment

An immutable historical simulation of one StrategyVersion under one explicit configuration. Captures: StrategyVersion, Instrument, parameter snapshot, DatasetSnapshot, date range, starting account state, Risk snapshot, simulation config, engine/version provenance, resulting trading facts. Completed Experiments are immutable. Running the same configuration again creates a new Experiment. Use Experiment, not Backtest/BacktestRun/BacktestResult.

## TradingAccount

Represents an external PAPER or LIVE broker account: broker, external account, account mode, base currency, capabilities/configuration. Historical Experiments do not create fake TradingAccounts; they use simulated account state.

## Account Modes

Canonical: PAPER, LIVE. OANDA Practice → PAPER. OANDA Live → LIVE.

## RiskProfile

A reusable definition of account-level Risk policy (risk per trade, max open positions, daily loss limit, max drawdown). May be editable. Experiments and Deployments must preserve immutable Risk configuration snapshots.

## Deployment

Assigns one StrategyVersion to one TradingAccount + one Instrument + one parameter snapshot + one Risk configuration for ongoing PAPER or LIVE execution. A Deployment is persistent configuration; the runtime process executing it is not the Deployment.

## Deployment States

Canonical states and lifecycle: [Deployment feature](../features/deployment.md).

## Deployment Configuration Immutability

A DRAFT Deployment may be edited. Once traded, changes to StrategyVersion, Instrument, TradingAccount, parameters, or Risk configuration should normally require a new or cloned Deployment.

## Active Deployment Invariant

Atlas v1 allows at most one active Deployment for a given TradingAccount + Instrument. Enforce in persistence, not only in UI.

## TradeIntent

An immutable Strategy request to change trading exposure. Initial actions: OPEN_LONG, OPEN_SHORT, CLOSE_POSITION, UPDATE_PROTECTION. NO_ACTION is a Strategy decision but does not become a persisted TradeIntent. Contains: StrategyVersion, context, Instrument, action, decision time, proposed stop/target, rationale. A TradeIntent is not an Order.

## Signal

Signal is not a canonical Atlas domain entity. If used informally in UI/explanation, it must not create a competing persisted model parallel to TradeIntent.

## RiskDecision

An immutable evaluation of a TradeIntent under current Risk policy and account/exposure state. Phases: PRE_FLIGHT, PRE_SUBMISSION. Outcomes: APPROVED, REJECTED. A TradeIntent may produce more than one RiskDecision.

## Order

Atlas's representation of an instruction intended for an execution venue or simulator. Order identity is Atlas-owned; external broker Order IDs are separate fields. Initial statuses: PENDING_SUBMISSION, SUBMITTED, PARTIALLY_FILLED, FILLED, CANCELED, REJECTED, EXPIRED, UNKNOWN. UNKNOWN means Atlas cannot currently establish venue state — not failure.

## Order Type / Purpose

Initial types: MARKET, STOP, LIMIT. Initial purposes: ENTRY, EXIT, STOP_LOSS, TAKE_PROFIT, PROTECTION_UPDATE. Purpose and type are distinct.

## OrderEvent

An immutable record of a meaningful Order lifecycle change (ORDER_SUBMITTED, ORDER_FILLED, etc.). Order stores current state; OrderEvent preserves lifecycle history. Atlas is not event-sourced.

## Fill (Authority)

A Fill is an immutable execution fact recording Order, executed quantity/price, execution timestamp, fee/cost, external execution identifier. One Order may have multiple Fills. **A Fill, not Order submission, changes actual exposure.**

## Execution

Execution is not a separate canonical persisted domain entity. Use Order + OrderEvent + Fill to represent execution lifecycle.

## Position

Atlas's current projection of economic exposure for a Deployment and Instrument. Directional states: FLAT, LONG, SHORT. A Deployment may have at most one Position. Position = current exposure, not historical episode.

## Trade

One exposure episode from flat → exposed → flat. References/derives from: StrategyVersion, context, Instrument, TradeIntent, Orders, Fills, entry/exit values, costs, P&L, R multiple, rationale, exit reason.

## Position vs Trade

These are intentionally separate: Position = what exposure exists now; Trade = the current or historical exposure episode. Do not use one object for both purposes.

## Environment Context

Trades may originate from EXPERIMENT, PAPER, or LIVE. Do not create separate entities (BacktestTrade, PaperTrade, LiveTrade). Use the same Trade model with explicit provenance.

## Exit Reason

Initial canonical exit reasons: TAKE_PROFIT, STOP_LOSS, MANUAL_CLOSE, RISK_EXIT, END_OF_EXPERIMENT. Order status alone is not a Trade exit reason. Add new reasons only when required.

## Journal

Journal is a feature/view over canonical Trade history. User-authored notes and tags may attach to Trade. See: [Journal](../features/journal.md).

## SystemEvent

An immutable operational fact (DEPLOYMENT_STARTED, BROKER_DISCONNECTED, MARKET_DATA_STALE, RECONCILIATION_REQUIRED, etc.). Distinct from Strategy decisions, TradeIntents, OrderEvents. Do not use as generic debug-log replacement.

## Strategy State

Durable state required to continue deterministic methodology after restart. Belongs to StrategyVersion + execution context. Must be small, serializable, version-compatible. See: [Strategy Contract](strategy-contract.md).

## Simulation Account / Broker Account Snapshot

Historical Experiments use simulated account state (not a TradingAccount). PAPER/LIVE may normalize broker state into Atlas account snapshot/value objects. Neither competes with TradingAccount identity.

## Metrics

Performance metrics (net return, Sharpe, drawdown, profit factor, expectancy, win rate) are derived analytics. Primary facts remain: Fills, Trades, costs, account/equity history.

## Market Bar

A canonical market-data value. Detailed time/price semantics: [Market Data Model](market-data-model.md). Do not create provider-specific Bar entities in the core domain.

## Key Relationships (diagram)

Conceptually: Strategy → StrategyVersion → (Experiment → Trades) OR (Deployment → TradeIntents → RiskDecisions → Orders → [OrderEvents, Fills] → Position → Trades → SystemEvents). This diagram is conceptual; not a requirement for one persistence relationship style.

## Core Invariants

- One Instrument per Deployment
- One Position per Deployment
- **No Pyramiding**: if Position exists, new OPEN_LONG/OPEN_SHORT rejected
- **No Partial Exits**: Atlas v1 does not support partial Position reduction as normal Strategy behavior; domain must tolerate partial broker Fills
- **Partial Fill vs Partial Exit**: different — Order may partially fill (supported), Strategy intentionally closing 30% of Position (deferred)
- **No Instant Reversal**: LONG → close → FLAT → later OPEN_SHORT (not direct reversal)
- **Broker Authority**: for PAPER/LIVE, broker is authoritative for Orders, Fills, Positions, account exposure, protection. Atlas Position is a projection that must be reconciled when uncertainty occurs.
- **Immutability**: StrategyVersion, completed Experiment, TradeIntent, RiskDecision, OrderEvent, Fill, completed Trade facts, SystemEvent, DatasetSnapshot are immutable once finalized. Order status and Position may change as new facts arrive.
- **Human-Readable Identity**: raw UUIDs must not become normal user-facing identity; use meaningful labels.

## Canonical Terms to Avoid

Do not introduce as parallel core models: Bot, Signal, BacktestRun, BacktestResult, BacktestTrade, PaperTrade, LiveTrade, BacktestOrder, PaperOrder, LiveOrder, Execution (as separate persisted entity — workflow/feature name is allowed), BrokerTrade, PortfolioPosition. If one appears needed, first determine whether an existing canonical concept owns that responsibility.

## Domain Evolution

New concepts only when existing ones cannot represent required behavior. Before introducing a new noun: identify missing responsibility → verify active roadmap requires it → check overlap → update this document. Do not allow implementation terminology to silently become product terminology.

## Unresolved Decisions (preserved for human confirmation)

- **STARTING state**: domain-model.md does not list STARTING; deployment.md includes it (may be runtime-internal or canonical)
- **Exit reasons**: domain-model.md lists MANUAL_CLOSE/RISK_EXIT; experiments.md omits them — experiments.md is correct for initial Experiment scope
- **"Execution" in Terms to Avoid**: Execution as a workflow/feature name is valid; Execution as a separate persisted domain entity is what is forbidden

## Success Criteria

The Domain Model is working when two independent coding agents can agree on: what a StrategyVersion/Experiment/Deployment is, when a TradeIntent exists, what RiskDecision represents, what an Order means, when a Fill changes exposure, how Position differs from Trade, which system owns broker truth — without creating parallel models.
