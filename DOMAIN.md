# Atlas Domain Laws

These are implementation-independent rules for Atlas. “Current” describes the
committed historical baseline. “Future boundary” is a safety requirement, not a
claim that PAPER or LIVE exists.

## Vocabulary

- A **Strategy** produces a hypothesis evaluation. A **StrategyVersion** is its
  immutable, identifiable implementation and parameter contract.
- An **Experiment** is a deterministic historical simulation with immutable
  inputs and completed evidence. Its market input is a **DatasetSnapshot**.
- A **TradeIntent** is a Strategy proposal handed to centralized **Risk**.
  Risk produces a **RiskDecision**; an **Order** may produce a **Fill**.
- A **Position** is financial exposure, and a **Trade** is its auditable lifecycle.
  Do not rename historical Experiments to “backtests”.

## Current laws

1. `StrategyVersion` identity, source provenance, and parameters are immutable.
2. An Experiment is reproducible from its immutable StrategyVersion, immutable
   DatasetSnapshot, period, parameters, risk configuration, and simulation facts.
   Completed inputs, results, and provenance do not change.
3. Time is explicit UTC. Requested periods are positive, minute-aligned, half-open
   ranges. Only completed candles are eligible for decisions.
4. Historical evaluation is chronological and no-lookahead. A completed analytical
   frontier is evaluated at most once; later observations cannot become earlier fills.
5. The current analytical contract is provider-native M15 MID. The current
   execution contract is sparse provider-native M1 BID/ASK. A required observation
   is never fabricated, interpolated, forward-filled, aggregated in place, or
   silently substituted with another resolution or price component.
6. Strategy code is pure at its boundary: it may determine setup, direction, stop
   proposal, target methodology, and rationale, but it does not access accounts,
   persistence, brokers, Risk, or UI.
7. Risk is centralized and owns exposure eligibility and sizing. Strategy does not
   size a trade or submit an Order.
8. Position state is derived from applied Fills, not inferred from Strategy state.
   Execution prices and their source observations remain auditable.
9. Invalid, incomplete, stale, contradictory, or unknown financial/data state fails
   closed. It must not be converted into a successful result, fill, or new exposure.

## Future safety boundaries

10. When broker execution exists, broker truth wins over local assumptions. An
    uncertain order submission is not blindly retried or treated as successful.
11. Any open broker exposure requires broker-hosted protection before new exposure
    is considered safe. Reconciliation is required before resuming after restart,
    timeout, or any uncertain financial state.
12. PAPER and LIVE must share these Strategy, Risk, accounting, and safety
    boundaries. These requirements do not authorize or describe a current broker
    execution workflow.
