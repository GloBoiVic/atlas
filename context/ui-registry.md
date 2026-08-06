# UI Registry

Living document. Updated after every component is built. Read this before building any new component — match existing patterns exactly before inventing new ones.

---

## How to Use

Before building any component:

1. Check if a similar component already exists here
2. If yes — match its exact classes
3. If no — build it following design.md and ui-tokens.md, then add it here

After building any component — update this file with the component name, file path, and exact classes used.

---

## Components

_Empty. Components will be added here as they are built._

### Backtests page panels

File: `frontend/src/app/backtests/backtests-view.tsx`
Last updated: 2026-08-04

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-surface`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `p-atlas-5 sm:p-atlas-6`, `gap-atlas-4`, `gap-atlas-6` |
| Typography       | semantic `text-atlas-*`, `font-atlas-semibold`, `leading-atlas-*`, `tracking-atlas-tight` |
| Hover state      | `hover:bg-atlas-bg-elevated`, `hover:bg-atlas-accent-dim`, `duration-atlas-base ease-atlas-out` |
| Shadow           | none |
| Accent usage     | `bg-atlas-accent`, `text-atlas-accent`, semantic positive/negative/warn tokens |

**Pattern notes:**
Backtest panels use restrained dark Atlas surfaces and 1px dividers. Numeric and
Decimal-string values use `font-atlas-mono`; status is always expressed with text and
a semantic color. Tables remain horizontally scrollable on narrow screens, while the
run form stacks fields and retains a full-width touch-safe submit target.

**Reconciliation notes:** Existing compact controls retain `py-[10px]` and the
touch-safe `min-h-11` target because no equivalent Atlas spacing or
control-height token exists. The empty-list breathing room retains `py-[56px]` for
the same reason. These are intentional exceptions, not new token candidates.

**Review-fix notes:** Decimal ratio values use a string-only percent shift at the
display boundary. `max_drawdown` remains an absolute monetary Decimal and is labeled
`Max drawdown (absolute)` rather than being presented as a percentage. Datetime-local
form values are explicitly interpreted as UTC before API serialization.

### Backtest status and metric primitives

Files: `frontend/src/app/backtests/status-badge.tsx`, `status-message.tsx`, `metric.tsx`
Last updated: 2026-08-04

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-*` semantic status surfaces; `bg-atlas-bg-elevated` for messages |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `p-atlas-4`, `px-[10px] py-atlas-1`, `py-atlas-3` |
| Typography       | `text-atlas-xs`, `text-atlas-md`, `text-atlas-lg`, `leading-atlas-snug` |
| Hover state      | none for display primitives |
| Shadow           | none |
| Accent usage     | semantic status tokens and `text-atlas-accent` |

**Pattern notes:** Status uses text plus semantic color. Metrics keep API Decimal
strings in `font-atlas-mono`; absolute monetary drawdown is labeled explicitly and
is not converted into a percentage.

### Journal page and entry rows

File: `frontend/src/app/journal/journal-view.tsx`
Last updated: 2026-08-05

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-surface`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `px-atlas-5 sm:px-atlas-6`, `py-atlas-5`, `gap-atlas-4`, `gap-atlas-5` |
| Typography       | `text-atlas-md`, `text-atlas-lg`, `text-atlas-xs`, `font-atlas-semibold`, `font-atlas-mono` |
| Hover/focus      | `hover:bg-atlas-bg-elevated`, `focus:ring-2 focus:ring-atlas-accent/30` |
| Shadow           | none |
| Accent usage     | `text-atlas-accent`, `bg-atlas-accent`, semantic positive/negative tokens |

**Pattern notes:** Journal rows prioritize identity, immutable Decimal-string trade facts, and
P&L. Signal and market context use a native disclosure panel so detail does not overwhelm the
scan path. Notes are the only editable field; saves are explicit, pending, and notified with
Sonner. Mobile rows stack while desktop preserves a scan-friendly data grid.

### Analytics page, metric grid, and equity curve

Files: `frontend/src/app/analytics/analytics-view.tsx`, `frontend/src/app/analytics/loading.tsx`,
`frontend/src/app/analytics/error.tsx`
Last updated: 2026-08-05

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-surface`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `p-atlas-5 sm:p-atlas-6`, `gap-atlas-4`, `gap-atlas-5`, `mt-atlas-6` |
| Typography       | `text-atlas-3xl`, `text-atlas-xl`, `text-atlas-lg`, `text-atlas-md`, `text-atlas-xs`, `font-atlas-semibold`, `font-atlas-mono` |
| Hover/focus      | `hover:bg-atlas-bg-elevated`, `focus:ring-2 focus:ring-atlas-accent/30` |
| Shadow           | none |
| Accent usage     | `text-atlas-accent`, `bg-atlas-accent`, semantic positive/negative tokens |

**Pattern notes:** Analytics preserves API Decimal strings for monetary values and total return;
only the chart's controlled SVG display boundary converts equity values for coordinates. Undefined
Sharpe and profit factor states use explicit “Not defined” copy with the reason, never zero or
infinity. Date-time controls are interpreted as UTC before query serialization. The equity curve
uses the API-provided closed-trade series and includes a visually hidden data table for accessible
point-by-point reading.

### Atlas application shell and top navigation

Files: `frontend/src/app/layout.tsx`, `frontend/src/components/layout/top-nav.tsx`
Last updated: 2026-08-05

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-bg-elevated`, `bg-atlas-accent-soft` |
| Border           | `border-b border-atlas-border`, `border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `h-atlas-topnav-height`, `px-atlas-page-gutter`, `gap-atlas-6`, `px-atlas-3` |
| Typography       | `text-atlas-sm`, `text-atlas-lg`, `font-atlas-medium`, `font-atlas-semibold`, `tracking-atlas-tight` |
| Hover/focus      | `hover:bg-atlas-bg-elevated`, `hover:text-atlas-fg`, `focus-visible:ring-2 focus-visible:ring-atlas-accent/40` |
| Shadow           | none |
| Accent usage     | `text-atlas-accent`, `bg-atlas-accent-soft` |

**Pattern notes:** The shell uses a persistent 56px desktop-first top bar with normal Next
`Link` navigation. Active routes are conveyed with a tinted Atlas accent surface and
`aria-current="page"`; nested routes remain active. Primary links scroll horizontally rather
than collapsing the operational desktop navigation. The shell status badge is explicitly
unavailable until a truthful backend status read model exists; it never invents trading state.

### Shell status and boundary primitives

Files: `frontend/src/components/ui/status-badge.tsx`,
`frontend/src/components/layout/shell-state.tsx`
Last updated: 2026-08-05

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg-elevated`, `bg-atlas-positive-dim`, `bg-atlas-negative-dim`, `bg-atlas-warn-dim` |
| Border           | `border border-atlas-border`, `border-atlas-border-strong` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `p-atlas-6`, `mt-atlas-2`, `mt-atlas-4`, `px-atlas-3`, `py-atlas-1` |
| Typography       | `text-atlas-xs`, `text-atlas-sm`, `text-atlas-xl`, `text-atlas-3xl`, `font-atlas-medium`, `font-atlas-semibold` |
| Hover/focus      | `hover:bg-atlas-bg-elevated`, `focus-visible:ring-2 focus-visible:ring-atlas-accent/40` |
| Shadow           | none |
| Accent usage     | semantic status tokens; no color-only status communication |

**Pattern notes:** Status badges pair semantic color with visible text and an optional icon.
Loading and error boundaries use calm, explicit copy and preserve the shell's neutral surfaces.
They are foundation primitives only; no dashboard, bot, market, or trading state is fabricated.

### Shell button primitive

File: `frontend/src/components/ui/button.tsx`
Last updated: 2026-08-05

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-accent`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border-strong` for outline |
| Border radius    | `rounded-atlas` |
| Text — primary   | `text-white`, `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `min-h-11`, `px-atlas-4`, `py-atlas-2` |
| Hover/focus      | `hover:bg-atlas-accent-dim`, `hover:bg-atlas-bg-elevated`, `focus-visible:ring-2 focus-visible:ring-atlas-accent/40` |
| Shadow           | none |
| Accent usage     | `bg-atlas-accent`, `text-white` |

**Pattern notes:** The button is a small Shadcn-style CVA primitive with default, outline, and
ghost variants. It is reserved for deliberate shell actions and does not imply trading state.

### Dashboard operational panels

Files: `frontend/src/app/dashboard/dashboard-view.tsx`, `frontend/src/app/dashboard/loading.tsx`,
`frontend/src/app/dashboard/error.tsx`
Last updated: 2026-08-05

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-surface`, `bg-atlas-bg-elevated`, `bg-atlas-warn-dim` |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `px-atlas-5`, `py-atlas-4`, `p-atlas-5`, `gap-atlas-6` |
| Typography       | `text-atlas-3xl`, `text-atlas-xl`, `text-atlas-lg`, `text-atlas-sm`, `text-atlas-xs`, `font-atlas-semibold`, `font-atlas-mono` |
| Hover/focus      | Existing `Button` outline primitive with `focus-visible:ring-2 focus-visible:ring-atlas-accent/40` |
| Shadow           | none |
| Accent usage     | `text-atlas-accent`, semantic positive/negative/warn tokens, `StatusBadge` |

**Pattern notes:** Dashboard panels display only API-provided account, position, bot, trade,
strategy-count, health, freshness, and analytics facts. Decimal strings remain strings and are
formatted with prefixes only; timestamps are explicitly labeled UTC. Empty, loading, error,
unavailable, stale, and polling states are visible. REST polling is the baseline until the
operational WebSocket slice lands. Tables remain horizontally scrollable on narrow screens.

### Bot management operational views

Files: `frontend/src/app/strategies/strategies-view.tsx`,
`frontend/src/app/strategies/bot-form.tsx`
Last updated: 2026-08-06

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-surface`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border`, `border-atlas-border-strong` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `p-atlas-5`, `p-atlas-6`, `px-atlas-5`, `py-atlas-4`, `gap-atlas-4` |
| Hover/focus      | `focus:ring-2 focus:ring-atlas-accent/30`, shared Button focus ring |
| Shadow           | none |
| Accent usage     | `text-atlas-accent`, semantic status tokens, `StatusBadge` |

**Pattern notes:** Bot rows expose exact account, mode, instrument, strategy-version identity,
observed status, desired status, and last successful UTC refresh. Paper/testnet views use the
same component with an explicit mode scope. Lifecycle commands are confirmed before dispatch;
the API response is invalidated/refetched rather than represented optimistically. Configuration
forms expose only the REST bot contract, allow paper/testnet only, and keep JSON strategy config
as an opaque API-owned object.

**Safety note:** The wire `Bot.mode` remains an open string. `isSupportedBotMode` narrows it at
runtime; unknown or production modes render no paper/testnet controls and cannot reach lifecycle
mutations or the editable configuration form.

### Trading confirmation dialog

File: `frontend/src/components/ui/confirm-dialog.tsx`
Last updated: 2026-08-06

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-surface`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas-md` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-sm`, `text-atlas-fg-secondary` |
| Spacing          | `p-atlas-6`, `p-atlas-4`, `gap-atlas-3` |
| Hover/focus      | shared Button focus ring |
| Shadow           | none |
| Accent usage     | `text-atlas-warn` for consequence copy |

**Pattern notes:** Native modal semantics (`dialog`, `showModal`, Escape cancellation) are used
for deliberate lifecycle confirmation. The body always lists bot, account, mode, instrument,
observed/desired state, and the consequence; text is paired with semantic color and iconography.

### Trades operational history and settings boundary

Files: `frontend/src/app/trades/trades-view.tsx`, `frontend/src/app/settings/page.tsx`
Last updated: 2026-08-06

| Property         | Class |
| ---------------- | ----- |
| Background       | `bg-atlas-bg`, `bg-atlas-surface`, `bg-atlas-bg-elevated` |
| Border           | `border border-atlas-border` |
| Border radius    | `rounded-atlas`, `rounded-atlas-md`, `rounded-atlas-pill` |
| Text — primary   | `text-atlas-fg` |
| Text — secondary | `text-atlas-fg-secondary` |
| Spacing          | `px-atlas-5`, `py-atlas-4`, `p-atlas-6`, `gap-atlas-3` |
| Typography       | `text-atlas-3xl`, `text-atlas-xl`, `text-atlas-lg`, `text-atlas-md`, `text-atlas-xs`, `font-atlas-semibold`, `font-atlas-mono` |
| Hover/focus      | shared `Button` focus ring; `hover:bg-atlas-bg-elevated` |
| Shadow           | none |
| Accent usage     | `text-atlas-accent`, semantic positive/negative/warn tokens, `StatusBadge` |

**Pattern notes:** Trades is a read-only, REST-polled table. API Decimal strings are displayed
without arithmetic, and entry/exit timestamps are labeled UTC. Loading, disconnected, empty, and
stale states remain scoped to the trade query. Settings intentionally uses the same restrained
panel pattern but exposes a truthful backend-prerequisite state rather than local-only controls.

### Lightweight Charts equity wrapper

File: `frontend/src/components/charts/equity-curve-chart.tsx`
Last updated: 2026-08-06

| Property         | Class / value |
| ---------------- | ------------- |
| Background       | chart surface uses Atlas `--color-atlas-surface` token |
| Border           | containing panel `border border-atlas-border` |
| Border radius    | `rounded-atlas` |
| Text — primary   | chart axis uses Atlas `--color-atlas-fg-secondary` |
| Text — secondary | chart grid/axis uses Atlas border tokens |
| Spacing          | `mt-atlas-3` around chart container |
| Hover/focus      | Lightweight Charts crosshair; accessible `role="img"` plus adjacent data table |
| Shadow           | none |
| Accent usage     | chart line uses Atlas `--color-atlas-accent` |

**Pattern notes:** The wrapper converts only API Decimal strings and UTC timestamps at the chart
display boundary, sends one bounded batch of at most 2,000 API points, observes responsive size,
and removes the chart/observer on cleanup. No candlestick wrapper is added because no candle REST
read model exists in the deployed API.
