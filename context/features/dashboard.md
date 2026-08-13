# Dashboard

## Purpose

Answers: What is Atlas doing right now, and does anything require attention? Reflects deliberately narrow initial scope: OANDA Practice, USD, EUR/USD, EMA Sweep Engulfing.

## Primary Hierarchy

1. safety/action-required state | 2. account and current exposure | 3. active Deployment | 4. current performance | 5. recent trading activity. Healthy infrastructure visually quiet.

## Header Context

Compact: OANDA Practice · PAPER · EUR/USD · ● Connected. No large system-health panel when healthy.

## Summary

Initial: Account Equity (USD, broker-authoritative), Today's P&L (+$125.40, +0.24% — canonical calculation, not dashboard-specific), Current Position (if flat: EUR/USD FLAT; if exposed: direction, units, entry, unrealized P&L, stop, target), Active Deployment (EMA v1, PAPER, RUNNING, EUR/USD, 15m, Risk 1%; actions: Pause/Resume/Stop when valid). Small number of compact groups — not KPI wall.

## Deployment State / Current Performance / Recent Trades

Canonical shared statuses (RUNNING, PAUSED, FAILED, RECONCILIATION_REQUIRED) — no dashboard-specific names. Simple equity curve (TradingView Lightweight Charts) secondary to exposure. Short recent Trades: Time, Direction, Entry/Exit, P&L, R. EUR/USD column unnecessary since single Instrument. Opens Trade in Journal.

## Recent Activity

Meaningful events only: Deployment started, Setup activated, TradeIntent approved, Order filled, Position closed, Paused. No heartbeats, data refreshes, internal worker activity, debug messages.

## Action Required / Safety Messages

Persistent safety issues take visual priority: OANDA disconnected, data stale, reconciliation required, protection missing, Deployment failed. Each explains: what happened, what Atlas did, exposure blocked? remaining protected? action available? ("Reconciliation required — OANDA reports EUR/USD exposure Atlas cannot match. New entries blocked. [Reconcile]"). Not toast-only.

## Healthy / No Position / No Deployment / Empty State

When healthy: compact "PAPER · OANDA Connected · Runtime Healthy". Flat: "No open position — Atlas monitoring EUR/USD for next valid setup." No active Deployment: "No active Deployment — Create a PAPER Deployment from a validated StrategyVersion." Before any activity: "Atlas is ready for research. Load EUR/USD data and run your first Experiment." No $0.00 metrics.

## PAPER vs LIVE / Navigation / Layout

PAPER mode always obvious. LIVE unmistakable when supported. Shared horizontal navigation from [Design](../design/design.md) — no sidebar. Structure: Top Nav → header + status → compact summary row → Position/Deployment → equity/performance context → recent Trades/Activity. Fewer sections when information doesn't warrant.

## Visual Density / Live Updates / Stale Values

Compact summary groups, one Position/Deployment section, one small chart, short recent-history tables. No KPI walls, multiple competing charts, order-book panels, infrastructure dashboards, nested cards. Update equity, unrealized P&L, Position, Deployment state, critical alerts via polling or WebSocket. No WebSockets solely for first Dashboard. Stale values → don't present as current; surface condition. Safety-sensitive uncertainty obvious.

## Derived Metrics / Actions / Manual Close / Design

Dashboard reuses canonical accounting/performance logic — no separate formulas in frontend. Allow only state-related actions (Pause/Resume, Open Trade, Reconcile); config-heavy workflows link to dedicated pages. Manual close (future) uses canonical execution with explicit confirmation — no frontend-only Position mutation. Dashboard screenshot/mockup is visual reference only; written context governs.

## Non-Goals

No multi-account portfolio dashboard, allocation charts, watchlists, economic calendar, news, order book, dozens of widgets, multi-Instrument Position grid, advanced analytics, infrastructure observability, configurable widget system.

## Required Tests

USD equity display, PAPER/OANDA Practice presentation, flat/long/short Position, active Deployment display, PAUSED/FAILED/RECONCILIATION_REQUIRED states, persistent critical alert, stale state presentation, recent Trade linking, empty Atlas/no Deployment states, canonical P&L consumed (not recalculated), live/polling update handling where implemented.

## Acceptance Flow

**Healthy**: Open → see PAPER/OANDA Practice → equity → Position/FLAT → Deployment → today's performance → recent Trades/activity.
**Unsafe**: Open → reconciliation required displayed prominently → exposure blocked → protection status explained → Reconcile action available.

## Success Criteria

Within seconds: Is Atlas connected? PAPER/LIVE? Equity? EUR/USD exposure? What Strategy running? Making/losing money? Safe to continue? Anything needing attention? — without dense terminal navigation.
