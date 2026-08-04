# Feature: 11 — UI — Dashboard & Core Pages

## Description

Functional operational dashboard for the single-user remote deployment. The MVP focuses on paper trading and Binance testnet validation, not production live trading.

## Dependencies

- 01 — Project Foundation
- 05 — Backtesting
- 07 — Execution Layer
- 08 — Live Data Streaming — real-time feed infrastructure consumed via Feature 09
- 09 — Live Trading (Paper + Testnet) — live paper/testnet data for dashboard display
- 10 — Journal & Analytics
- 12 — Bot Management

## Deliverables

- [ ] Dashboard: P&L, open positions, active bots, account info
- [ ] Strategies page: List deployed strategy versions and parameters
- [ ] Backtests page: Run backtests, view results, compare runs
- [ ] Paper Trading page: Monitor paper trading bots
- [ ] Testnet page: Monitor Binance testnet validation bots
- [ ] Trades page: Trade history
- [ ] Journal page: Journal entries with context
- [ ] Analytics page: Performance metrics and charts
- [ ] Settings page: Supported risk configuration and bot/account settings
- [ ] TradingView charts: Candlestick charts, equity curves
- [ ] WebSocket integration: Real-time updates on dashboard

## Technical Details

### Dashboard Layout

```tsx
// app/dashboard/page.tsx
export default function Dashboard() {
  return (
    <div className="grid grid-cols-12 gap-4">
      <div className="col-span-8">
        <EquityCurveChart />
        <OpenPositionsTable />
      </div>
      <div className="col-span-4">
        <AccountSummary />
        <ActiveBots />
        <RecentTrades />
      </div>
    </div>
  )
}
```

### Pages

The canonical MVP page and route inventory is defined in `context/design.md`. This feature implements those routes and their operational states.

### UI Integration

Use the canonical chart, WebSocket, Axios, TanStack Query, and Shadcn patterns in `context/library-docs.md`. This feature owns page behavior, routes, loading/error states, and acceptance criteria rather than duplicating library examples.

### UI Boundary

The UI displays persisted and live facts only. It never calculates trading decisions, risk
approvals, position sizes, or metric formulas. All trading-critical computation runs on the
backend. The UI consumes Feature 09 for real-time paper/testnet data and Feature 12 for bot
lifecycle controls.

## Acceptance Criteria

- [ ] Dashboard shows live P&L and positions
- [ ] All pages are functional and display correct data
- [ ] Charts render correctly with TradingView Lightweight Charts
- [ ] Real-time updates work via WebSocket
- [ ] Navigation between pages works
- [ ] Responsive layout works on different screen sizes
- [ ] Destructive trading actions require deliberate confirmation
- [ ] Cloudflare Access supplies authentication; the UI does not implement passwords

## Done when

All acceptance criteria are met.
