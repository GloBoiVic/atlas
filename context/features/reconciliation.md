# Reconciliation

## Purpose

Establishes whether Atlas local trading state agrees with authoritative broker state. For PAPER/LIVE: broker truth wins. Makes Atlas safe after runtime restart, network failure, request timeout, missed broker activity, uncertain Order state, Position mismatch, protection mismatch. Not a general synchronization framework.

## Core Principle

Atlas cannot prove trading state → uncertainty → block new exposure → establish broker truth → repair local projection where safe → resume only when state known. Never guess financial state.

## Scope / Authority

Initial: TradingAccount, Deployment, Orders, Fills, Position, broker-hosted protection. OANDA Practice, EUR/USD, PAPER. Authority: [Domain Model](../architecture/domain-model.md) — broker truth wins; Atlas should not overwrite it.

## When Reconciliation Runs

Runtime startup, Deployment START/RESUME, after uncertain Order submission, after broker reconnect, after detected state mismatch. Periodic lightweight may be added if needed. No high-frequency sync engine without need.

## Startup Rule / Inputs / Result

[Runtime Model](../architecture/runtime-model.md): no new exposure before reconciliation completes. Inputs: local (Deployment, desired/actual state, Orders, Fills, Position, open Trade, expected stop/target, Strategy state, last frontier) + broker (account, open trades/Positions, pending Orders, transaction history, protective instructions, external IDs). OANDA retrieval inside adapter. Result: MATCHED (agree sufficiently — trading may continue if other safety passes), REPAIRED (broker truth clear, safe to reconstruct — persist missing Fill, update Order/Position/Trade; repair preserves auditability), RECONCILIATION_REQUIRED (cannot safely determine or repair — unexplained exposure, ambiguous identity, quantity mismatch, missing protection, conflicting Orders, insufficient history → Deployment RECONCILIATION_REQUIRED, new exposure blocked, no auto-resume).

## Unknown Order

Submission timeout → Order UNKNOWN. Recovery: query broker with stable correlation/external evidence. Order found → normalize status, ingest Fills, update Position/Trade, verify protection. Order absent → must establish absence with strongest evidence before considering retry. Before retry: rerun PRE_SUBMISSION Risk — price/account/geometry may have changed. No blind resubmission of stale TradeIntent.

## Missed Fill / Fill Deduplication

Broker reports Fill Atlas doesn't have → deduplicate → persist → update Order → Position → Trade. Same canonical logic as real-time Fill handling. No separate reconciliation accounting. Use stable broker execution/transaction IDs. Repeated reconciliation must not duplicate Fill, Position qty, realized P&L, Trade history. Reconciliation itself must be idempotent.

## Position Match

Compare: Instrument, direction, executed quantity, other proof of exposure. Not only local Order status. Cases: **Local Position missing** (Atlas FLAT, OANDA LONG) → determine if belongs to Deployment; if reconstructable → repair; otherwise RECONCILIATION_REQUIRED. Don't auto-claim unknown exposure. **Broker Position missing** (Atlas LONG, OANDA FLAT) → inspect broker transaction history; if authoritative exit can be reconstructed → persist Fills, close Position/Trade; otherwise require reconciliation. **Quantity mismatch** (Atlas 50k, OANDA 30k) → use broker history to reconstruct; if unambiguous → repair; otherwise RECONCILIATION_REQUIRED. **Direction mismatch** (Atlas LONG, OANDA SHORT) → critical — new exposure blocked, Deployment RECONCILIATION_REQUIRED; don't auto-reverse.

## Unexpected Broker Exposure

Trader may act directly through OANDA. Atlas must not assume all activity originated from it. Unexpected conflicting TradingAccount+EUR/USD exposure → new Atlas exposure blocked. Manual/external trading = broker truth even when Atlas didn't initiate.

## Protection Verification

For every Atlas-managed open PAPER/LIVE Position requiring protection: verify expected broker-hosted protection. Missing stop → critical safety condition: block new exposure, Deployment FAILED or RECONCILIATION_REQUIRED, persistent alert. Never report healthy. Missing target → also mismatch; stop is primary. Incorrect protection → reconcile/repair only when intent unambiguous. Orphan protective Order (Atlas Position flat but protective Order could create unintended exposure) → critical — safely cancel/reconcile before normal trading resumes.

## Manual Activity / Initial Ownership Constraint

Tolerate user direct OANDA interactions. Detect resulting mismatch; don't assume exclusive control. v1 uses one OANDA Practice + EUR/USD → conservatively treat conflicting external EUR/USD activity as relevant to active Deployment. No complex attribution before needed.

## Strategy State / Data Frontier / Stale Opportunities

Broker reconciliation doesn't determine Strategy state. After external state reconciled: restore persisted Strategy state + required market-data catch-up separately. Don't infer setup state from broker Position. Last processed bar prevents duplicate evaluation per [Runtime Model](../architecture/runtime-model.md). Catch-up reconstructs state, not discover-and-execute historical signals. Stale missed entry → do not execute.

## Deployment State / PAUSED/STOPPED

During reconciliation: new exposure disabled. Only after reconciliation + other startup checks → actual state returns to RUNNING. PAUSED may reconcile while remaining PAUSED — reconciliation establishes truth, doesn't override intent. STOPPED should normally be flat; if exposure discovered → unexpected → RECONCILIATION_REQUIRED. Don't ignore exposure because desired state says STOPPED.

## Runtime Ownership / DB Transactions / Record

Only owning runtime may reconcile. Apply local repair operations transactionally (Fill + Order + Position + Trade in one coherent operation). Not held open during broker requests. Persist reconciliation record: Deployment, started_at, completed_at, result, trigger, summary. Detailed repair facts through existing canonical OrderEvents/Fills. No second event-sourcing system. Triggers: RUNTIME_START, DEPLOYMENT_START, DEPLOYMENT_RESUME, BROKER_RECONNECT, ORDER_UNKNOWN, STATE_MISMATCH, MANUAL_REQUEST.

## Repeated Reconciliation / Broker Unavailable / Reconnect

Running repeatedly against unchanged state must be safe — no duplicate Fills/Trades/Position changes/Order resubmits/Strategy resets. Broker unavailable → truth unavailable → incomplete → new exposure blocked. Don't resolve with stale cached state. Existing protection may continue but Atlas must not claim freshly verified. After reconnect: reconcile first → resume later.

## Safety Events / UI / Manual Reconcile

Safety events: [Safety Model](../architecture/safety-model.md). Material failures require persistent visibility beyond toasts. Healthy: understated ("Last reconciled 10:15 UTC"). When action required: elevated ("Reconciliation required: OANDA reports EUR/USD exposure Atlas cannot match. New entries blocked.") Manual Reconcile action runs same canonical process. v1 prefers surfacing ambiguous conditions over sophisticated state-editing UI. Block → explain → require external resolution → reconcile again.

## Non-Goals

No distributed reconciliation workers, auto broker failover, generalized multi-broker sync, complex state editor, auto-ownership of unrelated Trades, event-sourced reconstruction, auto-liquidation of every mismatch, self-healing heuristics that guess intent.

## Required Tests

Clean startup, repeated idempotent, restart with flat account, restart with open Position, missed Fill recovery, duplicate Fill prevention, UNKNOWN Order found/absent at broker, no blind retry, PRE_SUBMISSION rerun before retry, local FLAT/broker exposed, local exposed/broker FLAT, quantity/direction mismatch, unexpected manual exposure, stop protection confirmed, missing stop/target detected, orphan protection, broker unavailable, reconnect requires reconciliation, PAUSED remains after reconciliation, stale signal not executed, last bar prevents duplicate evaluation, ambiguous mismatch blocks exposure. Credential-dependent tests separate.

## Acceptance Scenarios

**Restart**: PAPER Position open → runtime stops → protection remains → runtime restarts → ownership acquired → exposure blocked → OANDA fetched → Orders/Fills/Position/protection reconciled → state restored → missed bars without stale entry → state safe → resumes.
**Submission Timeout**: ENTRY Order submitted → times out → Order UNKNOWN → no retry → query OANDA → original found → ingest result → no duplicate.
**Missed Fill**: Order SUBMITTED → OANDA reports Fill Atlas doesn't have → persist Fill → update Order → reconstruct Position/Trade → verify protection → REPAIRED.

## Success Criteria

Restart → establish OANDA truth → detect missing/conflicting state → safely repair unambiguous projections → block ambiguous exposure → verify protection → resume only after known state — without duplicate Orders/Fills, invented execution facts, or blind automatic recovery.
