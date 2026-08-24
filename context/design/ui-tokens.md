# Atlas V2 UI Tokens

## Authority and scope

This guide records the reusable semantic vocabulary evidenced by the approved
Atlas V2 mockups. It is design context only: it does not prescribe CSS,
Tailwind configuration, shadcn setup, chart options, application behavior, or
screen-specific implementation. Written context governs behavior and scope;
the approved PNGs govern V2 appearance; this guide and `visual-guide.md`
interpret recurring visual evidence without overriding either.

Atlas V2 is dark-first: a deep blue-black canvas, dark navy raised surfaces,
restrained cool-neutral text and borders, and sparse semantic color. Dark-first
does not mean a dense institutional terminal. Calm, spacious, low-noise,
technical presentation remains the goal.

## Naming rules

Canonical documentation identifiers use `atlas.<category>.<role>`. A future CSS
adapter may normalize these to `--atlas-<category>-<role>`. Framework aliases
are adapters, not additional source tokens. Admit a token only when its role
recurs across the mockups or established cross-screen conventions. Do not
create page, component, badge, lifecycle, PAPER, LIVE, or control colors when
an existing semantic role composes correctly.

## Core semantic color roles

| Token | Meaning and recurring use | Evidence status |
| --- | --- | --- |
| `atlas.color.background` | Application canvas and chart canvas. | Recurring dark canvas; exact value deferred. |
| `atlas.color.surface` | Panels, cards, tables, filter strips, and controls. | Recurring raised navy surfaces; exact value deferred. |
| `atlas.color.border` | Hairlines, dividers, gridlines, and control outlines. | Recurring muted blue-gray rules; exact value deferred. |
| `atlas.color.foreground` | Primary text and key neutral values. | Recurring cool near-white text; exact value deferred. |
| `atlas.color.foreground-muted` | Labels, supporting copy, timestamps, axes, and secondary navigation. | Recurring desaturated blue-gray text; exact value deferred. |
| `atlas.color.primary` | Selection, primary actions, information, links, active rules, and completed Experiment treatment. | Recurring electric blue/cyan role; exact value deferred. |
| `atlas.color.primary-foreground` | Foreground paired with primary surfaces or controls. | Pairing is semantic; contrast-tested value deferred. |
| `atlas.color.positive` | Healthy, connected, running, long, favorable values, up candles, target, and exit. | Recurring saturated green role; exact value deferred. |
| `atlas.color.positive-foreground` | Foreground paired with positive surfaces or controls. | Pairing is semantic; contrast-tested value deferred. |
| `atlas.color.negative` | Critical, stop, short, loss, adverse values, drawdown, down candles, and risk. | Recurring saturated red role; exact value deferred. |
| `atlas.color.negative-foreground` | Foreground paired with negative surfaces or controls. | Pairing is semantic; contrast-tested value deferred. |
| `atlas.color.warning` | Informative mismatch or caution that is not immediately critical. | Recurring amber role; exact value deferred. |
| `atlas.color.warning-foreground` | Foreground paired with warning surfaces or controls. | Pairing is semantic; contrast-tested value deferred. |
| `atlas.color.focus-ring` | Keyboard focus indication. | Existing convention may alias primary after contrast validation; exact treatment deferred. |

PAPER and completed lifecycle state use primary treatment where appropriate.
LIVE remains an environment distinction whose exact treatment is deferred
until an approved LIVE design exists. Color must not be the sole signal:
include text, icon, shape, position, or other redundant cue.

## Supporting semantic roles

These roles describe recurring hierarchy and reuse, not fixed values:

- Type: `atlas.type.page-title`, `atlas.type.section-title`,
  `atlas.type.body`, `atlas.type.label`, `atlas.type.metadata`,
  `atlas.type.metric`, `atlas.type.helper`.
- Layout: `atlas.layout.content-max`, `atlas.layout.page-gutter`,
  `atlas.layout.section-gap`, `atlas.layout.panel-padding`,
  `atlas.layout.control-height`, `atlas.layout.table-row-height`.
- Shape: `atlas.radius.panel`, `atlas.radius.control`,
  `atlas.radius.badge`, and `atlas.border.hairline-width`.

Exact font family/assets, weights, sizes, line heights, tracking, dimensions,
radii, and breakpoints are deferred. Approximate screenshot measurements are
evidence only and must not become normative values.

## Chart role aliases

Charts use the core semantic roles rather than an independent palette:

| Chart treatment | Atlas role |
| --- | --- |
| Equity line/area, EMA, entry | `atlas.color.primary` |
| Drawdown, down candles, stop | `atlas.color.negative` |
| Up candles, target, exit | `atlas.color.positive` |
| Grid | `atlas.color.border` |
| Axes | `atlas.color.foreground-muted` |
| Chart canvas | `atlas.color.background` / `atlas.color.surface` |
| Confirmation | `atlas.color.warning` |
| Reference | `atlas.color.foreground-muted` |

The violet Sweep treatment is a chart-local annotation observed in the journal
detail mockup. It is not a global token without recurring evidence.

## Future adapter examples (conceptual only)

A later Tailwind CSS v4 adapter may expose `@theme` aliases named
`--color-atlas-*`. A later shadcn-compatible adapter may map `background`,
`foreground`, `card`, `primary`, `destructive`, `border`, `input`, and `ring`
to Atlas roles. These are mapping examples, not CSS instructions or new source
values. Existing `--atlas-background`, `--atlas-ink`, `--color-atlas-blue`, and
ad-hoc utility colors are migration inputs, not authoritative V2 values.

## Evidence and deferred validation

The role extraction is based on the ten approved V2 PNGs listed in
`visual-guide.md`. Visual inspection establishes recurring roles and treatment,
not exact hex/OKLCH values, contrast ratios, typography metrics, responsive
breakpoints, or chart-library options. Those values require later implementation
and accessibility validation. Hover, focus, disabled, loading, error, empty,
disconnected, narrow-screen, tooltip, crosshair, and annotation-interaction
states are also deferred.
