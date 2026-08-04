# Feature: 05 — Backtesting

**Roadmap phase:** Phase 7. This feature is deliberately sequenced after Features 06 (Risk)
and 07 (Execution Layer) despite its lower domain ID.

## Description

Run a strategy against historical data and get performance results. Deterministic and fast.

## Dependencies

- 02 — Core Infrastructure
- 03 — Data Layer
- 04 — Strategy Engine
- 06 — Risk Engine
- 07 — Execution Layer

## Deliverables

- [ ] Backtester engine: Replays historical candles through the strategy pipeline
- [ ] Simulation clock integration: Controls time progression deterministically
- [ ] Simulated execution: Paper fills on historical data via the same Paper Broker used in live mode
- [ ] Historical replay: Loads candles from database (not from provider), emits CandleClosed events
- [ ] Dataset identity: Every backtest stores a dataset fingerprint for reproducibility
- [ ] BacktestRun and BacktestTrade models with run-level raw metrics persisted on BacktestRun
- [ ] Backtest persistence: Results stored in PostgreSQL (logically isolated from live/paper records)
- [ ] Run-level raw metrics stored on BacktestRun; canonical metric formulas owned by Feature 10
- [ ] Backtest API endpoints: POST /backtests, GET /backtests, GET /backtests/{id}
- [ ] Backtest UI: Run backtest, view results, compare runs

### Event Payload Status

The backtester emits `CandleClosed` events during replay. `CandleClosed` carries a
typed, keyword-only payload (`candle: Candle = field(kw_only=True)`) in
`backend/core/events.py`, so the backtester can emit these events and downstream
consumers can read `event.candle`. The backtester does **not** emit execution events
itself — the shared Paper Broker (via Feature 07) emits `OrderSubmitted`, `OrderFilled`,
`PositionOpened`, `PositionClosed`, and `TradeClosed` during replay.

## Technical Details

### Backtester Engine

The backtester replays one candle at a time through the same event-driven pipeline used by
live bots. Each candle is loaded from persistence (not from a provider), time is advanced
via the SimulationClock, and CandleClosed is emitted to trigger strategy → risk → execution.

```python
class BacktesterEngine:
    def __init__(
        self,
        event_bus: EventBus,
        strategy: Strategy,
        risk_engine: RiskEngine,
        execution_engine: ExecutionEngine,
        candle_repository: CandleRepository,
        simulation_clock: SimulationClock,
    ):
        self.event_bus = event_bus
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.execution_engine = execution_engine
        self.candle_repository = candle_repository
        self.clock = simulation_clock

    async def run(self, config: BacktestConfig) -> BacktestResult:
        # Load candles from persistence via instrument_id
        candles = await self.candle_repository.get_candles(
            instrument_id=config.instrument_id,
            timeframe=config.timeframe,
            start=config.start_date,
            end=config.end_date,
            price_basis="trade",
        )

        # Compute dataset fingerprint
        dataset_id = self._fingerprint(candles, config)

        # Process candles in chronological order. A signal confirmed at T
        # becomes eligible for a fill at the next candle open.
        for candle in candles:
            self.clock.advance(candle.open_time)
            await self.event_bus.publish(CandleClosed(candle=candle))

        # Collect results
        return self._compute_results(dataset_id)
```

**Key constraint:** The historical data loader (Feature 03) does **not** emit `CandleClosed`.
The backtester engine or replay process owns event emission.

### Dataset Identity / Fingerprint

```python
def _fingerprint(self, candles: list[Candle], config: BacktestConfig) -> str:
    """Return a deterministic hash of the input candle set."""
    import hashlib, json
    from datetime import timezone

    payload = {
        "instrument_id": str(config.instrument_id),
        "timeframe": config.timeframe,
        "price_basis": "trade",
        "candle_count": len(candles),
        "first_open": candles[0].open_time.astimezone(timezone.utc).isoformat(),
        "last_open": candles[-1].open_time.astimezone(timezone.utc).isoformat(),
        "prices": [(c.open_time.isoformat(), str(c.open), str(c.close)) for c in candles],
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
```

The dataset fingerprint is stored in `backtest_runs.dataset_id`. Two runs with the same
fingerprint, strategy commit, and configuration must produce identical results.

### BacktestRun Model

```python
@dataclass
class BacktestRun:
    id: UUID
    strategy_name: str
    strategy_version: str
    strategy_commit_sha: str
    strategy_parameters: dict
    instrument_id: UUID                   # FK to instruments; persistence identity
    symbol: str                           # resolved display name, e.g. "BTCUSDT"
    timeframe: str
    data_source: str
    dataset_id: str                       # fingerprint for reproducibility
    start_date: datetime
    end_date: datetime
    risk_config: dict
    execution_config: dict
    fill_model: str                       # "next_candle_open"
    status: BacktestStatus                # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    results: Optional[BacktestResult]
    created_at: datetime
    error_message: Optional[str]
```

### BacktestTrade Model

```python
@dataclass
class BacktestTrade:
    id: UUID
    backtest_run_id: UUID
    instrument_id: UUID                   # FK to instruments; persistence identity
    symbol: str                           # resolved display name, e.g. "BTCUSDT"
    direction: str
    entry_price: Decimal
    exit_price: Optional[Decimal]
    quantity: Decimal
    pnl: Optional[Decimal]
    entry_time: datetime
    exit_time: Optional[datetime]
    signal_metadata: dict
```

### Performance Metrics

Run-level raw metrics are persisted on `backtest_runs`. The *canonical metric formulas*,
return series, annualization policy, undefined-value handling, and open-trade treatment
are owned by Feature 10 (Journal & Analytics). Feature 05 may calculate and store the
same raw run metrics, but must cite Feature 10 for definitions and must not invent
alternate formulas.

**Numeric storage:** Monetary run metrics (total return absolute, max drawdown amount) use
`NUMERIC`/`Decimal`. Non-monetary ratios (Sharpe, profit factor) may use `FLOAT` but must
handle undefined cases (zero variance, no losing trades) explicitly.

**Recorded execution assumptions:** Every backtest run records its fee config, slippage
config, fill model (`next_candle_open`), protective-trigger ambiguity rule (stop-loss
first), strategy version commit, strategy parameters, risk configuration, dataset
fingerprint, and starting balance. This ensures metrics are reproducible from persisted
closed trades and the recorded configuration.

### Lookahead/Data-Integrity Gate

Before a backtest result is trusted:

1. **Completed-candle verification:** Confirm that no signal was generated from an
   incomplete candle (the engine gates this, but a post-run audit should validate).
2. **No-future-data review:** Verify that strategy logic does not reference candle data
   beyond the current candle's close time. Atlas should add an automated lookahead
   detection or sliced-recomputation validation gate analogous to Freqtrade's lookahead
   analysis.
3. **Deterministic reproduction:** Re-run with the same fingerprint and configuration;
   results must match exactly.

### Backtest API Endpoints

```python
@router.post("/backtests")
async def create_backtest(config: BacktestConfig) -> BacktestRun:
    ...

@router.get("/backtests")
async def list_backtests() -> list[BacktestRun]:
    ...

@router.get("/backtests/{backtest_id}")
async def get_backtest(backtest_id: UUID) -> BacktestRun:
    ...

@router.get("/backtests/{backtest_id}/trades")
async def get_backtest_trades(backtest_id: UUID) -> list[BacktestTrade]:
    ...
```

## Acceptance Criteria

- [ ] Backtest runs end-to-end: Historical data → Strategy → Risk → Execution → Metrics
- [ ] Backtest is deterministic: Same inputs produce same results
- [ ] Results persist and are viewable in UI
- [ ] Metrics use documented formulas, fees, slippage, and the configured fill model
- [ ] Backtest status is tracked (PENDING → RUNNING → COMPLETED/FAILED)
- [ ] Errors during backtest are captured in BacktestRun
- [ ] Same input dataset, strategy commit, configuration, and environment produce identical results
- [ ] Dataset fingerprint is computed and stored
- [ ] Backtest trades remain separate from paper/testnet orders, positions, trades, and journal entries
- [ ] Backtester emits CandleClosed events for each candle (Feature 03 does not)

## Done when

All acceptance criteria are met.
