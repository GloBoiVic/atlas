# Feature: 05 — Backtesting

## Description

Run a strategy against historical data and get performance results. Deterministic and fast.

## Dependencies

- 02 — Core Infrastructure
- 03 — Data Layer
- 04 — Strategy Engine
- 06 — Risk Engine
- 07 — Execution Layer

## Deliverables

- [ ] Backtester engine: Replays historical candles through strategy
- [ ] Simulation clock integration: Controls time progression
- [ ] Simulated execution: Paper fills on historical data
- [ ] BacktestRun and BacktestTrade models with run-level metrics persisted on BacktestRun
- [ ] Backtest persistence: Results stored in PostgreSQL
- [ ] Performance metrics: Total return, win rate, Sharpe ratio, max drawdown, profit factor
- [ ] Backtest API endpoints: POST /backtests, GET /backtests, GET /backtests/{id}
- [ ] Backtest UI: Run backtest, view results, compare runs

## Technical Details

### Backtester Engine

```python
class BacktesterEngine:
    def __init__(
        self,
        event_bus: EventBus,
        strategy: Strategy,
        risk_engine: RiskEngine,
        execution_engine: ExecutionEngine,
        data_provider: DataProvider,
        simulation_clock: SimulationClock,
    ):
        self.event_bus = event_bus
        self.strategy = strategy
        self.risk_engine = risk_engine
        self.execution_engine = execution_engine
        self.data_provider = data_provider
        self.clock = simulation_clock

    async def run(self, config: BacktestConfig) -> BacktestResult:
        # Load historical data
        candles = await self.data_provider.get_historical_candles(
            config.instrument, config.timeframe,
            config.start_date, config.end_date,
        )

        # Process candles in chronological order. A signal confirmed at T
        # becomes eligible for a fill at the next candle open.
        for candle in candles:
            self.clock.advance(candle.timestamp)
            await self.event_bus.publish(CandleClosed(candle=candle))

        # Collect results
        return self._compute_results()
```

### BacktestRun Model

```python
class BacktestRun:
    id: UUID
    strategy_name: str
    strategy_version: str
    strategy_commit_sha: str
    strategy_parameters: dict
    instrument: str
    timeframe: str
    data_source: str
    dataset_id: str
    start_date: datetime
    end_date: datetime
    risk_config: dict
    execution_config: dict
    fill_model: str  # next_candle_open
    status: BacktestStatus  # PENDING, RUNNING, COMPLETED, FAILED, CANCELLED
    results: Optional[BacktestResult]
    created_at: datetime
    error_message: Optional[str]
```

### BacktestTrade Model

```python
class BacktestTrade:
    id: UUID
    backtest_run_id: UUID
    instrument: str
    direction: str
    entry_price: Decimal
    exit_price: Optional[Decimal]
    quantity: Decimal
    entry_time: datetime
    exit_time: Optional[datetime]
    pnl: Optional[Decimal]
    signal_metadata: dict
```

### Performance Metrics

Run-level metrics are persisted on `backtest_runs`; the formulas and numeric policy are documented in the analytics feature and database schema.

### Backtest API Endpoints

```python
@router.post("/backtests")
async def create_backtest(config: BacktestConfig) -> BacktestRun:
    ...

@router.get("/backtests")
async def list_backtests() -> List[BacktestRun]:
    ...

@router.get("/backtests/{backtest_id}")
async def get_backtest(backtest_id: UUID) -> BacktestRun:
    ...

@router.get("/backtests/{backtest_id}/trades")
async def get_backtest_trades(backtest_id: UUID) -> List[BacktestTrade]:
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
- [ ] Backtest trades remain separate from paper/testnet orders, positions, and journal entries

## Done when

All acceptance criteria are met.
