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
