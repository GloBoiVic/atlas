# Feature: 13 — Polish & Testing

## Description

Remote single-user MVP hardening. Tests pass, failures fail closed, recovery is documented, and the testnet boundary is safe. Production live trading remains deferred.

## Dependencies

- All previous features

## Deliverables

- [ ] Unit tests: Core business logic (strategy, risk, execution)
- [ ] EventBus ordering, scoping, idempotency, and failure tests
- [ ] Integration tests: End-to-end backtest flow
- [ ] Bot restart and broker reconciliation tests
- [ ] Paper/testnet credential and endpoint safety tests
- [ ] Error handling refinement: All error paths tested
- [ ] Health monitoring: Contracts defined by Feature 02/08; validation and hardening here
- [ ] Lookahead/data-integrity validation gate: Automated check that backtest results
      contain no future-data violations
- [ ] Deterministic realism tests: Verify fee, slippage, fill model, and
      protective-trigger assumptions produce expected edge-case behavior
- [ ] Reconciliation tests: Unknown-order, partial-fill restart, and fail-closed recovery
- [ ] Endpoint safety tests: No production credentials reach browser or database;
      testnet mode cannot accidentally submit production orders
- [ ] Structured logging: All operations logged
- [ ] Documentation: Setup guide, architecture overview, API docs
- [ ] Performance testing: Backtester handles large datasets
- [ ] Deployment documentation: VPS, Docker Compose, Cloudflare Access, and Google login

## Technical Details

### Unit Tests

```python
# tests/test_strategy.py
class TestSMACrossoverStrategy:
    def test_buy_signal(self):
        strategy = SMACrossoverStrategy({"fast_period": 10, "slow_period": 50})
        candles = generate_uptrend_candles(100)
        signal = strategy.on_candle(candles[-1])
        assert signal is not None
        assert signal.direction == SignalDirection.BUY

    def test_no_signal_insufficient_data(self):
        strategy = SMACrossoverStrategy({"fast_period": 10, "slow_period": 50})
        candles = generate_uptrend_candles(5)
        signal = strategy.on_candle(candles[-1])
        assert signal is None
```

### Integration Tests

```python
# tests/test_backtest.py
class TestBacktester:
    @pytest.mark.asyncio
    async def test_full_backtest_flow(self):
        # Setup
        event_bus = EventBus()
        strategy = SMACrossoverStrategy({"fast_period": 10, "slow_period": 50})
        risk_engine = RiskEngine(event_bus, account_context, RiskConfig())
        broker = PaperBroker()
        execution_engine = ExecutionEngine(event_bus, broker, bot_id)
        # BacktesterEngine consumes candles from a repository, not a CSV provider.
        # Tests inject a pre-populated in-memory CandleRepository or use fixtures
        # that load test CSV data into it.
        candle_repository = InMemoryCandleRepository(test_candles)

        # Run backtest
        engine = BacktesterEngine(
            event_bus, strategy, risk_engine, execution_engine,
            candle_repository, SimulationClock(),
        )
        result = await engine.run(BacktestConfig(
            instrument_id=instrument_id,
            timeframe="1h",
            start_date=datetime(2024, 1, 1),
            end_date=datetime(2024, 6, 1),
        ))

        # Verify
        assert result.status == BacktestStatus.COMPLETED
        assert result.metrics.total_trades > 0
        assert result.metrics.win_rate >= 0
```

### Health Monitoring

```python
# tests/test_health.py
class TestHealthMonitor:
    def test_component_health_tracking(self):
        monitor = HealthMonitor()
        monitor.record_success("ExecutionEngine")
        assert monitor.get_status("ExecutionEngine") == HealthStatus.HEALTHY

    def test_degraded_after_failures(self):
        monitor = HealthMonitor(threshold=5)
        for _ in range(5):
            monitor.record_failure("ExecutionEngine", Exception("test"))
        assert monitor.get_status("ExecutionEngine") == HealthStatus.DEGRADED
```

### User and Deployment Documentation

This `docs/` directory is user-facing documentation generated from the engineering context; it does not replace the `context/` source-of-truth files.

```
docs/
├── setup.md           # How to set up the project
├── architecture.md    # Architecture overview
├── api.md            # API documentation
├── strategies.md     # How to write strategies
├── configuration.md  # Configuration reference
└── deployment.md     # How to deploy
```

## Acceptance Criteria

- [ ] All unit tests pass
- [ ] All integration tests pass
- [ ] `ruff check` passes
- [ ] `mypy` passes
- [ ] `npm run lint` passes
- [ ] Error handling works for all failure scenarios
- [ ] Health monitoring shows correct component status
- [ ] Documentation is complete and accurate
- [ ] Backtester handles 1 year of hourly data without issues
- [ ] No test requires production broker credentials or live orders

## Done when

All acceptance criteria are met.
