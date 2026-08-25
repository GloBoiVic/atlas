# Experiment Foundation Recovery

Status: approved; implementation READY gate in progress.

## Scope

Recover the V2-only historical Experiment vertical slice for EUR/USD/OANDA Practice,
using native M15 MID analysis, sparse M1 BID/ASK execution, immutable deterministic
snapshots, truthful gap outcomes, and the existing UI acceptance flow. PAPER/LIVE,
new providers/instruments, generalized frameworks, and legacy V1 compatibility are
out of scope.

## Approved context

- `EXPLORATION.md` — read-only live-path findings and blockers.
- `ARCHITECTURE.md` — authoritative approved blueprint, including amendments.
- User confirmation received 2026-08-25.

## Ordered tasks

1. Requirement contract: make `required_historical_context_bars` authoritative and
   remove `warm_up_bars` from the current persisted/domain path.
2. V2-only acquisition/persistence: native M15 plus sparse M1 BID/ASK, immutable
   membership/fingerprint, clean migration/reset treatment where necessary.
3. Clock/configuration: evaluate every analytical frontier once and enforce the exact
   bounded entry bucket `[frontier, frontier + 1 minute)`.
4. Runner/accounting: explicit execution-gap consequences, chronological protection,
   canonical TradeIntent → RiskDecision → Order → Fill → Position → Trade.
5. Lifecycle/API/frontend: V2 provenance, quality/gap disclosure, completed and
   zero-trade states.
6. Tests and real OANDA UI acceptance run.

Status: pending READY receipt.
