# Exploration — Phase 3: First Historical Trade

- Roadmap exit: deterministic LONG and SHORT simulated Trades through `M15 Bar → Strategy → TradeIntent → RiskDecision → Order → Fill → Position → Trade` (`context/roadmap/roadmap.md:21-23`).
- Phase 2 is terminally closed; immutable DatasetSnapshot membership and snapshot-only deterministic M15 derivation are available.
- Strategy is pure, accepts completed EUR/USD MID M15 bars, and produces long/short decisions with stop and target methodology. No Experiment, Risk, execution, financial Position, Order, Fill, Trade, account, or simulator exists.
- Invariants: SimulatedAccount—not TradingAccount; Strategy cannot size or submit; Fill alone changes exposure; long uses ASK/BID and short uses BID/ASK; Decimal only; one Position/no pyramiding.
- Risks: signal/post-decision M1 reuse creates lookahead; broad historical execution realism belongs to Phase 4. Unsupported intrabar behavior must fail, not fabricate a Fill.
- Recommendation: backend-only, persisted one-Trade proof model with two isolated golden Experiments. The authoritative plan is `PHASE-3-BLUEPRINT.md`.
