# Atlas Domain Laws

This file contains only durable Atlas semantics that should survive implementation changes.

It does not describe application architecture, database tables, API shapes, runtime sequencing, feature plans, or future implementation designs.

## Strategy and methodology

1. A **Strategy** evaluates market information and produces trading intent. It does not authorize capital exposure.

2. **Risk** is separate from Strategy and is authoritative for whether new exposure is permitted and how permitted exposure is sized.

3. A **StrategyVersion** represents immutable methodology identity. Its implementation provenance and parameter contract must not silently change after persistence.

4. The meaning of the same StrategyVersion must remain consistent across Experiment, PAPER, and LIVE. Environment differences may affect execution facts, but must not silently redefine the methodology.

5. Strategy execution remains bounded by Atlas contracts. Strategy code must not directly own broker access, persistence, account authority, Risk, UI, or unrestricted platform capabilities.

## Time and market data

6. Trading decisions may use only information that was available at the decision frontier. Lookahead is prohibited.

7. Strategy evaluation may use only completed analytical observations required by its contract.

8. The same completed analytical frontier must not produce duplicate evaluation through replay, retry, reconnect, or restart.

9. Required market-data products and provenance remain explicit. Atlas must not fabricate, interpolate, forward-fill, or silently substitute a required observation.

10. Derived market data must not be represented as provider-native data.

11. Missing, stale, contradictory, incomplete, or otherwise uncertain required market data remains uncertainty. It must not be converted into a valid trading fact.

## Experiments and evidence

12. An **Experiment** is a deterministic historical simulation using preserved methodology, data provenance, configuration, and execution assumptions.

13. Completed Experiment inputs, results, and provenance are immutable historical evidence.

14. Historical evidence must remain reproducible and inspectable. Later implementation changes must not silently rewrite what a completed Experiment meant or observed.

## Risk, execution, and exposure

15. A **TradeIntent** is not an Order and does not create financial exposure.

16. An **Order** request does not prove execution.

17. Financial exposure is derived from confirmed **Fill** facts. Position state must not be invented from Strategy state, Order intent, or assumed broker behavior.

18. Execution pricing must use the correct executable market side for the action being taken.

19. Unknown, stale, contradictory, partial, or failed financial state blocks new exposure unless authoritative state proves that exposure is safe.

20. Atlas must not guess an uncertain Order outcome or blindly retry a submission whose broker outcome is unknown.

## Broker authority and protection

21. When broker execution exists, broker-confirmed external state is authoritative for actual broker exposure.

22. Atlas-local state may explain or project broker facts, but it must not override contradictory broker truth.

23. Reconciliation is required before resuming exposure-creating operation after restart, disconnect, timeout, uncertain submission, ownership loss, or other uncertain broker state.

24. Broker reconciliation must apply relevant authoritative broker facts before advancing any durable recovery cursor or claiming that reconciliation succeeded.

25. Open broker exposure must remain protected according to the active Risk and execution contract. Loss of optimistic local state must not remove required broker-side protection.

26. Failure to prove safe broker, financial, protection, or reconciliation state must fail closed rather than be converted into permission for new exposure.

## Trader control

27. Starting Atlas does not itself authorize trading.

28. Creating or changing capital exposure, activating PAPER or LIVE, changing broker/account credentials, or changing Risk policy requires explicit trader approval.

29. Atlas Risk remains authoritative for individual RiskDecision outcomes under the trader-approved Risk policy.
