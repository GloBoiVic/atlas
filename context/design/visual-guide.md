# Atlas V2 Visual Guide

## 1. Authority, scope, and dark-first character

The approved V2 PNGs are the canonical visual references for appearance. Written
context governs behavior and product scope. `ui-tokens.md` and this guide
interpret recurring evidence; neither authorizes navigation or behavior changes.

The visual character is dark-first, calm, spacious, restrained, technical, and
precise: deep blue-black canvas, dark navy surfaces, cool-neutral text and
borders, and sparse semantic color. Avoid dark-terminal density, gradients,
ornamental shadows, decorative motion, excessive green/red, and dashboard tile
walls.

## 2. Approved screenshot inventory

1. `context/design/atlas-overview-page.png`
2. `context/design/atlas-strategies-page.png`
3. `context/design/atlas-strategies-details-page.png`
4. `context/design/atlas-experiments-page.png`
5. `context/design/atlas-experiments-detail-page.png`
6. `context/design/atlas-experiment-run-page.png`
7. `context/design/atlas-compare-experiments-page.png`
8. `context/design/atlas-deployments-page.png`
9. `context/design/atlas-journal-page.png`
10. `context/design/atlas-journal-detail-page.png`

These ten files are references, not screen specifications.

## 3. Shell and hierarchy

Use a shallow global header with Atlas wordmark, horizontal navigation, active
section shown by restrained blue emphasis and an underline, and persistent
PAPER plus OANDA Practice / Connected context. A search or keyboard-shortcut
affordance may appear as shown in the references; the screenshots do not change
navigation behavior. There is no sidebar.

Use a wide desktop-first content region with generous, consistent gutters. A
page header establishes one primary question through a prominent title, short
supporting context, and at most one clear primary action. Keep the hierarchy
scannable rather than filling the canvas.

## 4. Typography and financial numbers

The hierarchy is: prominent page/detail title; medium section or panel title;
compact uppercase metadata/table labels; regular body and numeric values; and
smaller muted helper text and timestamps. Key financial values may be larger,
brighter, or semantic in color, but labels and provenance remain subdued.
Exact family, weights, sizes, line heights, and tracking are deferred.

## 5. Color semantics and state presentation

Use the semantic roles in `ui-tokens.md`: blue for selection, action,
information, links, and active rules; green for healthy/running/positive/long;
red for critical/loss/stop/short; amber for informative mismatch or caution;
neutral roles for content. PAPER is visibly distinct; LIVE treatment is not
defined beyond preserving an unmistakable environment distinction when later
approved.

Connection and lifecycle states stay inline and persistent where relevant:
small dots plus text, badges, or values. Pair color with text, icon, shape, or
position so it is never the sole signal. Persistent safety conditions explain
what happened, what Atlas did, whether new exposure is blocked, whether current
exposure is protected, and the next action. Sonner is transient feedback only.

## 6. Surfaces, borders, shape, and rhythm

Prefer dark raised panels with thin hairline outlines, modest corner rounding,
compact rectangular controls, and restrained badges. Tables use aligned columns,
generous row height, and visible horizontal rules. Use spacing rhythm and
selective panels to preserve air around the dominant content region. Do not use
gradients, ornamental shadows, glow, or highly rounded decorative containers.
Exact spacing, radii, border width, and control dimensions are deferred.

## 7. Recurring patterns

- Page headers combine title, context, and a single primary action when needed.
- Panels hold account summaries, charts, focused forms, comparisons, and detail;
  avoid nested card grids and decorative tile walls.
- Tables use muted compact headers, aligned values, row rules, semantic badges,
  and understated selection or pagination.
- Filter/search controls sit in one bordered strip above list tables.
- Tabs are inline and restrained, with blue active text and a bottom rule.
- Buttons distinguish bright blue filled primary actions from dark outlined
  secondary actions; operational Pause is blue outlined and Stop is red.
- Badges and connection/running dots are compact; status text remains present.
- Forms may use numbered vertical steps, grouped bordered sections, and a
  persistent experiment summary rail.
- Activity and timeline rows use thin-line technical icons with visible text;
  source/event color is supplemental, not the only meaning.

## 8. TradingView chart treatment

Use a dark chart canvas, faint horizontal gridlines, subdued axes, and compact
in-panel controls. Equity is a bright blue line with a restrained translucent
blue area; drawdown is a red line with restrained translucent red area below
zero. Trade charts use green/red candles, a blue EMA, and dashed horizontal
entry, target, and stop levels with matching labels.

Annotations are explicit but bounded: Reference, Sweep, Confirmation, Entry,
Exit, Target, and Stop. Confirmation is warning-colored, Reference is muted,
and Sweep's violet treatment remains chart-local. Grid, axes, series, and levels
map to the semantic roles in `ui-tokens.md`. Exact opacity, sizing, tooltip,
crosshair, axis formatting, interaction, and accessibility representation are
deferred.

## 9. Safety, accessibility, and unknown states

Safety and connection conditions remain visible in the relevant shell, panel, or
row. Color is redundant with text and iconography. Later implementation must
validate foreground/background contrast and keyboard focus treatment, retain
reduced-motion support, and define hover, focus, disabled, loading, error,
empty, disconnected, narrow-screen, tooltip, crosshair, and annotation states.
The wide references do not establish responsive breakpoints or overflow rules.

## 10. Anti-patterns and migration boundaries

Do not introduce sidebar navigation, dense institutional-terminal styling,
gradient or ornamental-shadow decoration, excessive semantic color, nested card
grids, speculative screen-specific tokens, or controls merely to fill space.
Do not infer behavior, copy, data, navigation, or application requirements from
a screenshot-only difference.

This guide does not authorize edits to `frontend/`, CSS, Tailwind or shadcn
configuration, chart code, dependencies, mockups, or product/feature context.
Application adoption is a separate workstream requiring exact-value selection,
contrast testing, and visual regression.

## 11. Per-mockup validation matrix

| Mockup | Shell / hierarchy | Recurring patterns | Semantic evidence | Chart evidence |
| --- | --- | --- | --- | --- |
| Overview | Horizontal shell, PAPER/Connected context, clear overview header. | Account summary, selective panels, recent activity/trades. | Positive/negative values remain sparse and meaningful. | Blue equity line with subdued grid and area treatment. |
| Strategies | Same shell and focused page-header hierarchy. | Strategy table/list with restrained controls and status treatment. | Blue selection/action; neutral metadata. | Not a dominant chart reference. |
| Strategy details | Same shell; detail title and restrained tabs. | Overview, versions, experiments, deployments pattern. | Version/status labels use text plus semantic treatment. | Not a dominant chart reference. |
| Experiments | Same shell and list-first hierarchy. | Bordered filter strip, aligned table, lifecycle badges. | Completed uses outlined primary treatment; metrics stay semantic. | Not a dominant chart reference. |
| Experiment detail | Detail header with inline tabs and selective panels. | Result summary and two-chart composition. | Return/health versus drawdown remain distinct. | Equity blue; drawdown red with restrained fills. |
| Experiment run | Clear form header and main workflow hierarchy. | Numbered steps, grouped fields, persistent summary rail. | Validation/completion and risk cues are redundant with text. | Chart is secondary to the run workflow. |
| Compare experiments | Comparison-first detail hierarchy. | Bordered comparison matrix and focused controls. | Different Strategy Version uses amber warning treatment. | Chart evidence is secondary/not dominant. |
| Deployments | Persistent shell state and operational page header. | Deployment table/detail, compact Pause and Stop actions. | Connected/Running/Active green; Stop red; PAPER explicit. | Not a dominant chart reference. |
| Journal | List-first header and scan-friendly table hierarchy. | Search/filter strip, trade rows, semantic direction/result values. | BUY/positive green and SELL/negative red with text labels. | Not a dominant chart reference. |
| Journal detail | Detail header with tabs and chart/summary hierarchy. | Trade summary, rationale, execution lineage, notes/tags, timeline. | Entry/exit/risk states use labels and semantic cues. | Candles, EMA, levels, and bounded Reference/Sweep/Confirmation annotations. |
