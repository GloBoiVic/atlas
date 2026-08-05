# Feature: 10 — Journal & Analytics

## Description

Record completed trades with context. Calculate performance metrics from persisted trade data.

## Dependencies

- 02 — Core Infrastructure
- 07 — Execution Layer (Trade lifecycle, TradeClosed event)
- 04 — Strategy Engine

## Deliverables

- [ ] Journal service: Subscribes to TradeClosed, creates journal entries idempotently
- [ ] Journal model: Linked to trade, bot, account, strategy version; includes signal and market context
- [ ] Journal API endpoints: GET /journal, GET /journal/{id}
- [ ] Analytics service: Reads from persisted trade records, calculates metrics
- [ ] Performance metrics: Total return, win rate, Sharpe ratio, max drawdown, profit factor, per-strategy
- [ ] Analytics API endpoints: GET /analytics
- [ ] Journal UI: View trade history with context
- [ ] Analytics UI: Performance charts and metrics
- [ ] Notes can be added to journal entries

## Technical Details

### Journal Service

### Event Payload Gap

`TradeClosed` event class is currently defined with `pass`. It must carry a `trade: Trade`
payload field before the journal service can read `event.trade` to create journal entries.

The journal subscribes to `TradeClosed` events rather than individual fill or position events.
This ensures each completed trade produces exactly one journal entry.

```python
class JournalService:
    def __init__(self, event_bus: EventBus, repository: JournalRepository):
        self.event_bus = event_bus
        self.repository = repository
        self.event_bus.subscribe(TradeClosed, self._on_trade_closed)

    async def _on_trade_closed(self, event: TradeClosed):
        trade = event.trade
        # Idempotent: if a journal entry already exists for this trade_id, skip.
        existing = await self.repository.get_by_trade_id(trade.id)
        if existing is not None:
            return

        entry = JournalEntry(
            trade_id=trade.id,
            account_id=trade.account_id,
            bot_id=trade.bot_id,
            strategy_version_id=trade.strategy_version_id,
            instrument=trade.instrument,
            direction="long" if trade.direction == "buy" else "short",
            entry_price=trade.entry_price,
            exit_price=trade.exit_price,
            quantity=trade.quantity,
            pnl=trade.net_pnl,
            strategy_name=trade.strategy_name,
            signal=trade.signal_metadata,
            market_conditions=trade.market_context,
            opened_at=trade.entry_time,
            closed_at=trade.exit_time,
        )
        await self.repository.save(entry)
```

### Journal Entry Model

The canonical journal schema and relationships are defined in `context/database.md`. Key points:

- Journal entries reference a `trade_id` (not a `position_id`) as the canonical anchor.
- Entries are created on `TradeClosed` and are idempotent by `trade_id`.
- Notes are human-authored and can be added/updated independently of trade events.
- Market context (broader market state at entry/exit) is captured from the trade record.

### Analytics Service

```python
class AnalyticsService:
    def __init__(self, repository: JournalRepository):
        self.repository = repository

    async def get_metrics(self, start_date: datetime, end_date: datetime) -> PerformanceMetrics:
        entries = await self.repository.get_closed_entries(start_date, end_date)

        total_trades = len(entries)
        winning_trades = len([e for e in entries if e.pnl and e.pnl > 0])
        losing_trades = len([e for e in entries if e.pnl and e.pnl < 0])

        total_pnl = sum((e.pnl for e in entries if e.pnl is not None), Decimal("0"))

        # Calculate return-series metrics using Decimal money values.
        # Sharpe ratio: mean(returns) / std(returns) * sqrt(periods_per_year)
        # Max drawdown: peak-to-trough decline in cumulative equity
        # Profit factor: gross_profit / gross_loss
        ...

        # Serialization policy across the API boundary:
        #   Monetary values (total_pnl, max_drawdown)    → decimal strings
        #   Decimal ratios  (total_return)               → decimal strings (exact precision)
        #   Float ratios    (win_rate, sharpe_ratio,      → float
        #                    profit_factor)
        #
        # starting_equity and ending_equity are the configured starting balance and
        # the computed ending balance (starting_equity + total_pnl). Both are Decimal.
        return PerformanceMetrics(
            total_return=str(total_return) if total_return is not None else None,
            total_pnl=str(total_pnl) if total_pnl is not None else None,
            starting_equity=str(starting_equity) if starting_equity is not None else None,
            ending_equity=str(ending_equity) if ending_equity is not None else None,
            win_rate=winning_trades / total_trades if total_trades else 0.0,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=str(max_drawdown) if max_drawdown is not None else None,
            profit_factor=profit_factor,
            total_trades=total_trades,
            winning_trades=winning_trades,
            losing_trades=losing_trades,
        )
```

### Canonical Metric Definitions

Feature 10 owns the canonical metric formulas. Feature 05 may store raw run-level snapshots
but must cite these definitions and must not invent alternate formulas.

- **Total return:** Normalized cumulative return as an exact Decimal ratio
  (`0.125` = 12.5%). Formula: `(ending_equity - starting_equity) / starting_equity`.
  Includes fees and slippage.

- **Total P&L (`total_pnl`):** Absolute net realised P&L (`ending_equity - starting_equity`).
  A Decimal monetary value. Includes fees and slippage.

- **Starting equity:** The configured initial balance at the start of the period. Decimal.

- **Ending equity:** The computed balance at the end of the period
  (`starting_equity + total_pnl`). Decimal.

- **Win rate:** closed winning trades / all closed trades. Zero when there are no closed
  trades. Open trades are excluded.

- **Profit factor:** gross winning net P&L / absolute gross losing net P&L. **Undefined**
  when there are no losses — represented explicitly (not as a misleading zero or infinity).

- **Max drawdown:** largest peak-to-trough decline in the marked equity curve. **Default
  basis:** closed-trade equity for canonical MVP analytics. Open-trade treatment (marked
  equity including unrealized P&L) is shown separately, not mixed. The source series must
  be recorded.

- **Sharpe ratio:** `mean(periodic_excess_return) / std(periodic_excess_return) *
  sqrt(annualization_factor)`. **Recommended MVP defaults:** daily equity returns,
  risk-free rate = zero, annualization factor = `sqrt(365)` (Binance Spot 24/7).
  Require a minimum-observation rule (e.g., at least 30 daily returns). Explicitly
  report `undefined` for zero variance or insufficient samples.

- **Numeric storage:** Three categories:
  - **Monetary values** (P&L, drawdown amounts, starting_equity, ending_equity) — `NUMERIC`/`Decimal`.
  - **Decimal ratios** (total_return) — `NUMERIC`/`Decimal`. Ratios, not monetary values,
    but stored as Decimal for exact precision.
  - **Float ratios** (win_rate, Sharpe, profit factor) — `FLOAT` per coding-standards policy.

  Each category must define serialization and undefined-value behavior explicitly.

- **Fees and slippage:** Deducted at the fill level and reflected in trade `net_pnl`.
  The configured fee and slippage values are recorded per run.

- **Open trade exclusion:** Open trades are excluded from all canonical metrics until
  they close. Marked-equity analytics that include unrealized P&L may be provided as a
  separate view.

- **Metric reproducibility:** All metrics must be reproducible from persisted closed
  trades and the recorded starting balance, fee/slippage config, fill model, dataset
  fingerprint, strategy commit, and parameter snapshot.

### API Endpoints

```python
@router.get("/journal")
async def list_journal_entries(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    bot_id: Optional[UUID] = None,
) -> list[JournalEntry]:
    ...

@router.get("/journal/{entry_id}")
async def get_journal_entry(entry_id: UUID) -> JournalEntry:
    ...

@router.patch("/journal/{entry_id}/notes")
async def update_journal_notes(entry_id: UUID, notes: str) -> JournalEntry:
    """Update notes on a closed trade entry."""
    ...

@router.get("/analytics")
async def get_analytics(
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
) -> PerformanceMetrics:
    ...
```

## Acceptance Criteria

- [ ] Completed trades are automatically journalized on TradeClosed
- [ ] Journal entries include trade identity, strategy, signal, and market context
- [ ] Journal writes are idempotent (same trade_id does not create duplicate entries)
- [ ] Analytics calculate documented metrics from persisted closed trades
- [ ] Metric formulas define return series, annualization, drawdown basis, fees, and open-trade treatment
- [ ] Notes can be added to journal entries independently
- [ ] Journal and analytics are viewable in UI
- [ ] Open trades are excluded from metrics until close
- [ ] Journal references trade_id (canonical anchor), not position_id

## Done when

All acceptance criteria are met.
