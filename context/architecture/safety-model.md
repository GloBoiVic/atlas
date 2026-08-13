# Safety Model

## Purpose

The Safety Model defines how Atlas behaves when trading state is uncertain, degraded, or unsafe. Core rule: if Atlas cannot prove new exposure is safe, new exposure is blocked. Safety must be consistent across Risk, Deployment, Execution, Reconciliation, Runtime, and UI.

## Safety Priorities

1. protect existing exposure | 2. prevent unintended new exposure | 3. establish broker truth | 4. preserve auditability | 5. resume only when safe. Convenience must not override trading safety.

## Exposure Classes

**New exposure**: OPEN_LONG, OPEN_SHORT, increasing position size. **Existing exposure**: current Position. **Risk-reducing actions**: close Position, preserve/restore stop, cancel unsafe duplicate entry. Safety blocks should generally prevent new exposure without preventing legitimate risk reduction.

## Fail-Closed Rule

When required state is unknown: new exposure → BLOCKED. Examples: broker state unknown, Position uncertain, unresolved Order, stale market data, account unavailable, reconciliation incomplete, runtime ownership uncertain. Do not guess.

## Canonical Unsafe States

**PAUSED**: controlled non-entry — no new entries, existing protection remains, risk-reducing actions allowed, market data may continue. **FAILED**: error preventing safe execution — new exposure blocked, failure persisted, broker protection remains, no automatic speculative recovery. **RECONCILIATION_REQUIRED**: local state cannot be proven against broker truth — new exposure blocked, broker state queried, unresolved mismatches visible. Do not resume simply because runtime process is healthy.

## Broker Disconnect / Reconnect

Broker connectivity lost → new exposure BLOCKED. Existing protection untouched. Surface affected account, Deployments, connection state, last known state, protection status. Do not assume disconnect means Orders disappeared. Reconnect alone does not restore trading. Required: reconnect → fetch state → reconcile → confirm protection → validate market data → resume if safe.

## Unknown Order State

If Atlas cannot determine whether Order exists/filled: Order → UNKNOWN. Do not blindly resubmit. Block conflicting new exposure. Reconcile with stable client/external identifiers. UNKNOWN does not mean rejected.

## Submission Timeout / Duplicate Prevention

Submit → network timeout → mark uncertain → query broker → locate Order by stable correlation ID. Only retry if original did not succeed and retry is safe. Network uncertainty must never produce: timeout → blind retry → duplicate entry.

## Position Uncertainty / Unexpected Broker Exposure

If Atlas Position and broker disagree: Deployment → RECONCILIATION_REQUIRED. Do not silently overwrite and continue. Persist expected state, observed state, mismatch type, timestamp. If broker reports unattributed exposure: new automated exposure → BLOCKED. Do not automatically claim ownership of unknown exposure.

## Missing Protection / Protection After Entry

If open Position unexpectedly lacks required protection: CRITICAL SAFETY CONDITION → block new exposure, persist SystemEvent, surface prominently, attempt only defined risk-reducing behavior. If entry fills but protective Order creation fails: Deployment → FAILED or RECONCILIATION_REQUIRED. New exposure blocked. Attempt smallest safe corrective action. Do not leave Position silently unmanaged.

## Protective Order Preservation

Atlas shutdown, pause, or runtime failure must not automatically cancel valid broker-hosted protective Orders. Protection should outlive Atlas uptime whenever the broker supports it.

## Market Data Staleness

For active Deployment, required data must be current enough for valid decision. Stale → new exposure BLOCKED. Stale thresholds derived from market/timeframe behavior, not one global timeout.

## Runtime Loss

If atlas-runtime stops unexpectedly: broker-hosted protection remains, new automated exposure stops, local in-memory state untrusted until restored, startup reconciliation required. Do not rely on graceful shutdown.

## Runtime Ownership / Strategy State Failure

One runtime owns automated Deployments. If uncertain/duplicated: new exposure BLOCKED. Second runtime must not silently take control. If Strategy state missing/corrupt/incompatible: new exposure BLOCKED. Do not reset active state silently.

## Strategy Error / Risk Failure

Strategy evaluation unexpected error → Deployment FAILED. No new exposure. Existing protection remains. Risk cannot establish required state → RiskDecision REJECTED. Unknown → rejection.

## Risk Limits / Live vs Paper

Risk thresholds exceeded → new exposure BLOCKED. Not automatic liquidation. Safety semantics same across PAPER and LIVE. Do not weaken behavior for OANDA Practice.

## Manual External Trading / Stale Entry / Catch-Up

Assume user may modify broker account manually → unexpected changes → RECONCILIATION_REQUIRED. Old TradeIntent after downtime → do not blindly execute. State reconstruction and executable opportunity are separate concerns.

## End-of-Experiment Safety

Experiments are deterministic simulations not requiring broker safety controls, but must still reject impossible/undefined behavior.

## Error Classification / User-Facing Contract

Classify: VALIDATION, MARKET_DATA, BROKER_CONNECTION, EXECUTION, RISK, RECONCILIATION, STRATEGY, RUNTIME, PERSISTENCE. Avoid one generic state. For material failures UI answers: What happened? What did Atlas do? Is exposure protected? Is new exposure blocked? What next?

## Persistent vs Transient / SystemEvents

Transient: Sonner. Persistent safety conditions remain visible until resolved. Important safety events produce immutable SystemEvents (BROKER_DISCONNECTED, POSITION_MISMATCH, PROTECTION_MISSING, etc.). Not every debug message.

## Recovery Principle / Automatic Recovery

Conservative: detect → establish truth → repair safe stale projection → verify prerequisites → resume. Avoid: error → sleep → retry forever → auto-resume. Automatic recovery acceptable only when well-understood, idempotent, does not increase exposure, results in known safe state. Must not bypass reconciliation after state uncertainty.

## Human Intervention / Kill Switch

When Atlas cannot safely infer correct state → expose problem. Global emergency "block new exposure" control may be added; purpose is simple: prevent new entries, not liquidate Positions.

## Safety Invariants

UNKNOWN broker state → no new exposure. Missing required protection → no new exposure. Stale required market data → no new exposure. Failed reconciliation → no new exposure. Invalid Strategy state → no new exposure. Runtime ownership conflict → no new exposure. Risk-reducing actions remain allowed where safely possible.

## Required Tests

At minimum: broker disconnect blocks exposure, reconnect requires reconciliation, UNKNOWN Order prevents blind resubmission, duplicate Order prevention, Position mismatch blocks exposure, unexpected broker Position, missing protective stop, protection failure after entry, stale market data, Strategy evaluation failure, invalid Strategy state, runtime ownership conflict, Risk state unavailable, PAUSED allows risk reduction, FAILED preserves protection, stale catch-up TradeIntent not executed, persistent safety condition visible to API/UI, safe auto-recovery does not bypass required reconciliation.

## Success Criteria

Proven when Atlas consistently behaves: known+valid+reconciled → trading may proceed; unknown/stale/contradictory/unsafe → new exposure blocked, existing exposure protected, state surfaced, recovery explicit — without silently guessing or increasing risk under uncertainty.
