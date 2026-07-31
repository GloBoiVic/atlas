# Feature: 10 — Journal & Analytics

## Description

Record trades with context. Calculate performance metrics.

## Dependencies

- 02 — Core Infrastructure
- 07 — Execution Layer
- 04 — Strategy Engine

## Deliverables

- [ ] Journal service: Subscribes to trade events, records context idempotently
- [ ] Journal model: Entry price, exit price, P&L, strategy, notes, market conditions
- [ ] Journal API endpoints: GET /journal, GET /journal/{id}
- [ ] Analytics service: Subscribes to trade events, calculates metrics
- [ ] Performance metrics: Total return, win rate, Sharpe ratio, max drawdown, profit factor, per-strategy performance
- [ ] Analytics API endpoints: GET /analytics
- [ ] Journal UI: View trade history with context
- [ ] Analytics UI: Performance charts and metrics

## Technical Details

### Journal Service

```python
class JournalService:
    def __init__(self, event_bus: EventBus, repository: JournalRepository):
        self.event_bus = event_bus
        self.repository = repository
        self.event_bus.subscribe(OrderFilled, self._on_fill)
        self.event_bus.subscribe(TradeClosed, self._on_trade_closed)

    async def _on_fill(self, event: OrderFilled):
        entry = JournalEntry(
            instrument=event.order.instrument,
            direction=event.order.side,
            entry_price=event.fill_price,
            quantity=event.order.quantity,
            strategy=event.order.strategy_name,
            signal=event.order.signal_metadata,
            opened_at=event.timestamp,
        )
        await self.repository.save(entry)

    async def _on_trade_closed(self, event: TradeClosed):
        entry = await self.repository.get_by_position_id(event.position.id)
        entry.exit_price = event.position.current_price
        entry.exit_time = event.timestamp
        entry.pnl = event.position.unrealized_pnl
        entry.notes = event.notes
        await self.repository.update(entry)
```

### Journal Entry Model

The canonical journal schema and relationships are defined in `context/database.md`. This feature owns journal behavior and analytics formulas.

### Analytics Service

```python
class AnalyticsService:
    def __init__(self, repository: JournalRepository):
        self.repository = repository

    async def get_metrics(self, start_date: datetime, end_date: datetime) -> PerformanceMetrics:
        entries = await self.repository.get_closed_entries(start_date, end_date)

        total_trades = len(entries)
        winning_trades = len([e for e in entries if e.pnl > 0])
        losing_trades = len([e for e in entries if e.pnl < 0])

        total_pnl = sum((e.pnl for e in entries), Decimal("0"))
        average_win = np.mean([e.pnl for e in entries if e.pnl > 0]) if winning_trades else 0
        average_loss = np.mean([e.pnl for e in entries if e.pnl < 0]) if losing_trades else 0

        # Calculate documented return-series metrics using Decimal money values.
        ...

        return PerformanceMetrics(
            total_return=total_pnl,
            win_rate=winning_trades / total_trades if total_trades else 0,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            profit_factor=profit_factor,
            total_trades=total_trades,
        )
```

### API Endpoints

```python
@router.get("/journal")
async def list_journal_entries(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> List[JournalEntry]:
    ...

@router.get("/journal/{entry_id}")
async def get_journal_entry(entry_id: UUID) -> JournalEntry:
    ...

@router.get("/analytics")
async def get_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> PerformanceMetrics:
    ...
```

## Acceptance Criteria

- [ ] Trades are automatically journalized on fill/close
- [ ] Journal entries include strategy, signal, and market context
- [ ] Analytics calculate documented metrics from persisted closed trades
- [ ] Journal and analytics are viewable in UI
- [ ] Notes can be added to journal entries
- [ ] Replayed events do not create duplicate journal entries
- [ ] Metric formulas define return series, annualization, drawdown basis, fees, and open-trade treatment

## Done when

All acceptance criteria are met.
