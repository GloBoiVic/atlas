# Atlas — Design System

> This document defines the visual language, interaction patterns, and user experience principles for Atlas.
>
> Atlas should feel like a purpose-built trading application — not a generic SaaS dashboard.

---

## 1. Design Philosophy

Atlas is built around one principle:

> **Trading software should be powerful without feeling complicated.**

Atlas should feel:

- Modern
- Professional
- Calm
- Focused
- Fast
- Precise
- Trustworthy

Atlas should **not** feel:

- Like a generic SaaS admin panel
- Like a spreadsheet
- Like a legacy broker terminal
- Like a Bloomberg clone
- Overly flashy or overly dense

The interface should communicate confidence and control.

---

## 2. Primary UX Principle

Every screen should answer one primary question.

| Screen | Primary Question |
|--------|------------------|
| Dashboard | How is my trading doing right now? |
| Strategies | What strategies/bots do I have and what are they doing? |
| Backtests | Does this strategy work under historical conditions? |
| Paper Trading | How are paper bots behaving against live market data? |
| Testnet | Is the broker execution path behaving correctly? |
| Trades | What trades have occurred? |
| Journal | What happened and what can I learn from it? |
| Analytics | How is my trading performing over time? |
| Settings | How is Atlas configured? |

---

## 3. Desktop-First

Atlas is a desktop-first application. The primary use case is a trader at a desktop or laptop, potentially with multiple monitors.

The interface should take advantage of larger screens for charts, tables, strategy monitoring, and side-by-side information.

Atlas should still be usable on smaller screens, but mobile is not the primary design target for the MVP.

Do not sacrifice the desktop experience to achieve unnecessary mobile parity.

---

## 4. Application Shell

Atlas uses a persistent application shell with top-tab navigation.

```text
┌──────────────────────────────────────────────────────────┐
│ Atlas    Dashboard  Strategies  Backtests  Trades  ...   │
├──────────────────────────────────────────────────────────┤
│                                                          │
│                      Main Content                        │
│                                                          │
└──────────────────────────────────────────────────────────┘
```

Top navigation is used instead of a sidebar because:

- Atlas has a focused set of operational pages
- Trading data needs horizontal space (charts, tables)
- Desktop-first means wide screens where top tabs work well
- Less visual noise — focus stays on the data

Navigation layout:

```text
Left:   Logo / Brand
Center: Dashboard | Strategies | Backtests | Paper | Testnet | Trades | Journal | Analytics
Right:  Settings | Account
```

Canonical MVP routes:

| Page | Route |
|------|-------|
| Dashboard | `/dashboard` |
| Strategies | `/strategies` |
| Backtests | `/backtests` |
| Paper Trading | `/paper` |
| Testnet | `/testnet` |
| Trades | `/trades` |
| Journal | `/journal` |
| Analytics | `/analytics` |
| Settings | `/settings` |

The user should always understand:

1. Where they are.
2. What they are looking at.
3. What they can do next.

---

## 5. Dashboard

The dashboard is the primary operational view.

It answers: **"How is my automated trading doing right now?"**

The dashboard should prioritize:

- Current P&L
- Open positions
- Active bots
- Account balance
- Recent trades
- System status

Potential structure:

```text
┌───────────────────────────────────────────────────────┐
│ Overview                                               │
│                                                       │
│ Balance       Equity        Today's P/L    Open Pos.  │
│ $25,420       $25,812       +$392          3           │
├───────────────────────────────────────────────────────┤
│ Active Strategies                                     │
│                                                       │
│ BTC Breakout       Running      +$210       42 trades │
│ EMA Trend          Running      +$182       31 trades │
│ London Breakout    Paused       -$42        18 trades │
├───────────────────────────────────────────────────────┤
│ Open Positions                                       │
│                                                       │
│ Symbol    Strategy       Side    P/L       Status     │
│ EUR/USD   EMA Trend      Long    +$84      Open       │
│ BTC/USD   Breakout       Short   +$132     Open       │
└───────────────────────────────────────────────────────┘
```

Do not overcrowd the dashboard. Detailed analytics belong elsewhere.

---

## 6. Information Hierarchy

Atlas prioritizes information according to importance.

### Level 1 — Immediate

Information the trader needs at a glance:

- P&L
- Position state
- Bot state
- Connection state
- Account state

### Level 2 — Context

Information needed to understand Level 1:

- Strategy
- Symbol
- Timeframe
- Entry price
- Current price
- Position size
- Stop-loss / Take-profit

### Level 3 — Detail

Information useful for investigation:

- Order IDs
- Execution timestamps
- Raw broker data
- Event history

Level 3 information should not dominate the primary interface. Use progressive disclosure.

---

## 7. Status System

Atlas has a consistent status language across the application.

Status values:

```text
Running | Paused | Stopped | Starting | Stopping | Error
Connected | Disconnected | Pending | Filled | Rejected
Open | Closed | Live | Stale
```

Status is communicated through:

- Text
- Iconography
- Color

Never rely on color alone. Always pair color with text (e.g., red dot + "Stopped").

---

## 8. P&L Presentation

P&L is one of the most important pieces of information.

Display both:

- Absolute P&L: `+$428.40`
- Percentage P&L: `+1.72%`

P&L should always have clear context:

- Today
- Strategy
- Trade
- Position
- Account
- Selected date range

Avoid ambiguous labels such as simply `Profit`.

---

## 9. Color Usage

Color communicates meaning, not decoration.

Use semantic colors for:

- Positive performance (green)
- Negative performance (red)
- Warning (yellow/amber)
- Error (red)
- Active state (blue)
- Neutral (gray)

Do not make the entire interface green and red simply because it is a trading application. The primary visual language should remain neutral.

Color should be used sparingly so meaningful states remain visually significant.

Never use color as the only method of conveying information.

---

## 10. Typography

Typography prioritizes readability and information hierarchy.

Use a restrained typographic scale:

1. Page title
2. Section title
3. Important metric
4. Supporting information
5. Metadata

Numerical data (P&L, prices, quantities, percentages, balances) should be visually easy to scan.

Use tabular/monospaced numerical presentation where appropriate to prevent numbers from visually shifting.

Do not overuse monospace typography throughout the interface.

---

## 11. Charts

Charts are important but should remain purposeful. Charts answer specific questions.

### Strategy Chart

> Where did the strategy enter and exit?

Overlays:

- Entry/exit markers
- Stop-loss / Take-profit levels
- Strategy signals

### Equity Curve

> How has the strategy/account performed over time?

### Drawdown Chart

> When and how severely did performance decline?

Do not add indicators simply because a chart library supports them.

Charts should support:

- Timeframe selection
- Zoom / Pan
- Crosshair
- Hover details

Chart interactions should feel immediate. Do not overload charts with every available piece of information.

---

## 12. Tables

Tables are appropriate for:

- Trades
- Positions
- Strategies
- Backtests
- Orders
- Journal entries

Tables should prioritize scanability.

Common columns:

```text
Symbol | Strategy | Side | Entry | Exit | Size | P&L | Status | Time
```

Avoid showing every available database field. Advanced information can be exposed through detail views.

---

## 13. Forms

Forms should be simple and focused. Use sensible defaults. Group related settings.

Do not expose advanced configuration unless necessary.

```text
Strategy Settings

Symbol
Timeframe
Risk Per Trade

Advanced
  Position Limits
  Trading Hours
  Execution Settings
```

Use progressive disclosure for advanced settings.

---

## 14. Real-Time Updates

Atlas contains real-time trading information. The UI should update without requiring manual refresh when practical.

Examples:

- P&L
- Position price
- Bot status
- Order status

WebSockets should be used where appropriate for real-time updates. REST remains appropriate for normal request/response workflows.

Real-time data should communicate its freshness:

```text
Live | Updated 2s ago | Data delayed | Connection lost
```

Critical trading information should never create false confidence.

---

## 15. Trading Safety

Atlas is software capable of initiating financial transactions. The UI must prioritize deliberate user intent.

Destructive actions require confirmation:

- Close position
- Stop live bot
- Delete strategy
- Cancel order

Confirmation dialog example:

```text
Close Position?

BTC/USD
Long
0.25 BTC

Current P/L: +$127.40

This will submit a market order to close
the current position.

[Cancel] [Close Position]
```

The confirmation should clearly communicate what will happen.

After an action, the interface should communicate state:

```text
Starting... → Running
```

Or if it fails:

```text
Unable to start bot
Reason: Broker connection unavailable
```

Never leave the user wondering whether an action succeeded.

---

## 16. Environment Awareness

Atlas should make the current trading environment obvious.

A user should always know whether they are operating in:

```text
BACKTEST | PAPER | LIVE
```

Live mode should never visually resemble a harmless backtest.

The environment should be visible in the top navigation bar and in confirmation dialogs.

---

## 17. Consistency

The same concept must look and behave the same throughout Atlas.

If `Running` is represented one way on the Dashboard, it should look the same everywhere.

If a confirmation dialog uses a specific structure, destructive dialogs should follow the same pattern elsewhere.

Consistency reduces cognitive load.

---

## 18. Final Design Rule

When a design decision is unclear, ask:

> **Does this make Atlas easier for a trader to understand and operate?**

If yes, consider it.

If no, remove it.

When choosing between simple + clear and complex + feature-rich, prefer **simple + clear** unless the additional complexity provides meaningful trading value.

Atlas should feel like a tool that gets out of the trader's way.

> **Less interface. More control.**
