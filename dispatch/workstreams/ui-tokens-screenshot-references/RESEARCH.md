# Research: UI Tokens + Screenshot References

Independent visual-evidence supplement for `ui-tokens-screenshot-references`. The PNG observations below are visual approximations from the approved screenshots, not sampled source values or implementation specifications.

## 1. Approved mockup inventory

The required inventory is complete: ten PNGs are present directly under `context/design/`, each matching `atlas-*-page.png`:

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

The screenshots consistently depict the same Atlas workstation shell: Atlas wordmark, horizontal navigation, PAPER environment, OANDA Practice / Connected status, and a search/keyboard shortcut affordance.

## 2. Recurring visual color roles

These are approximate visual ranges observed across all ten PNGs. They are intentionally labeled approximations; they are not authoritative hex/OKLCH values.

| Recurring role | Approximate appearance | Evidence |
| --- | --- | --- |
| App background | Very deep blue-black, approximately `#020b16–#061321` | All ten screenshots; especially the unfilled areas in `atlas-strategies-page.png` and `atlas-deployments-page.png` |
| Raised surface / card | Slightly lighter navy, approximately `#071625–#0b1a2a` | Repeated cards, tables, filters, and detail panels in all screenshots |
| Hairline border/divider | Muted blue-gray, approximately `#17283a–#233449` | Card outlines and table row rules throughout; clear in `atlas-experiments-page.png` |
| Primary text | Cool near-white, approximately `#e7edf5–#f5f7fb` | Page headings, key values, and table names throughout |
| Secondary text | Desaturated blue-gray, approximately `#8e9caf–#aab4c3` | Supporting copy, labels, timestamps, and navigation; clear in `atlas-experiment-run-page.png` |
| Primary/selected action | Bright electric blue/cyan, approximately `#078ff0–#21c3ff` | Active nav underline/text, primary buttons, selected controls, chart line, and links |
| Positive/healthy/long | Saturated green, approximately `#00c978–#20e889` | Connected dots, running/active states, BUY/long labels, positive returns, and approved state |
| Negative/critical/short | Saturated red, approximately `#f13b43–#ff4c52` | Drawdown, losses, SELL/short labels, stop action, and risk/stop annotations |
| Warning | Amber/yellow, approximately `#e8a400–#ffbf19` | Different Strategy Version notice and Confirmation annotation in `atlas-compare-experiments-page.png` / `atlas-journal-detail-page.png` |
| Supplemental annotation | Purple/violet, approximately `#7d43d2–#b55cff` | Sweep marker and first timeline event in `atlas-journal-detail-page.png` |

Color is semantic and sparse rather than decorative: blue establishes selection/action/information, green communicates favorable or healthy state, red communicates loss/risk/stop, and amber communicates a warning. Neutral content remains neutral. This is consistent with the role guidance in `context/design/design.md` §Color / PAPER vs LIVE / Connection State, while the screenshots provide the dark surface context.

## 3. Typography

- The screenshots use a clean sans-serif with rounded, contemporary forms. Large page titles are bold and prominent; supporting descriptions are visibly smaller and muted. This is observable in every page header, for example `atlas-overview-page.png` and `atlas-experiments-page.png`.
- The apparent hierarchy recurs as: large page/detail title; medium panel/section title; compact uppercase metadata/table labels; regular body and numeric values; smaller muted helper text and timestamps.
- Key financial values use larger or brighter type and semantic color, while labels and provenance remain subdued. Positive/negative numbers are not made visually dominant by decoration beyond color and weight.
- Navigation and controls are compact, with selected navigation represented by bright blue text and an underline rather than oversized tabs. Detail-page tabs follow the same restrained treatment (`atlas-strategies-details-page.png`, `atlas-experiments-detail-page.png`).
- Exact font family, weight files, line-height, and letter-spacing cannot be established from rendered PNGs alone. The existing prose says visual intent, not a concrete type specification (`context/design/design.md` §§Visual Character, Page Header).

## 4. Spacing, shape, and layout

- The composition is desktop-first and wide, with generous outer margins and consistent horizontal alignment. Major content begins below a shallow global header; page headers have substantial separation before the principal panel.
- Cards and tables use thin outlines, dark surfaces, and modest corner rounding. The shape language is restrained: no gradients, ornamental shadows, or highly rounded pill containers are apparent.
- Controls generally have compact rectangular fields/buttons with modest rounding. Status badges and BUY/SELL labels are tighter rounded rectangles; dots are used for connection and running states.
- Most pages use one dominant content region, with selective two-column layouts: overview chart over two lower panels; experiment detail has two charts; run-experiment has a main form plus summary rail; journal detail has a chart/summary row and three lower panels.
- Tables use strong column alignment, generous row height, and visible horizontal rules. Filter/search controls are grouped in one bordered strip above the table (`atlas-experiments-page.png`, `atlas-journal-page.png`).
- The screenshots show a stable horizontal top nav with no sidebar. Active section is indicated by blue text and a blue bottom rule. The top-right PAPER badge and broker connection status are persistent shell context.
- Screens appear to share a large desktop canvas (visually about 1440px wide); exact screenshot dimensions and breakpoint behavior are not treated as token evidence here.

## 5. Recurring components and information patterns

- Global shell: Atlas wordmark, horizontal navigation, active-section underline, PAPER badge, OANDA Practice/Connected indicator, and search shortcut button.
- Page header: title, one-line explanatory context, and—where relevant—a single primary action at the right (Create Strategy, Run Experiment).
- Bordered panel/card: used for account summary, charts, forms, comparison matrix, detail summaries, and activity sections. The screenshots avoid a wall of small decorative tiles.
- Tables: column headers in compact uppercase/muted treatment, row separators, semantic badges, aligned financial values, and understated pagination or selection actions.
- Buttons: bright blue filled primary actions; dark outlined secondary actions; outlined blue or red operational actions where the state warrants it. The deployment Stop action is explicitly red; Pause is blue outlined (`atlas-deployments-page.png`).
- Tabs: inline, restrained, with blue active text and bottom rule. They appear in strategy detail, experiment detail, and journal detail contexts.
- Form workflow: numbered vertical steps at left, bordered grouped sections, compact controls, and a persistent experiment summary card (`atlas-experiment-run-page.png`).
- Status indicators: small colored dots plus text (“Connected”, “Running”, “Active”), outlined blue completion badges, and green/red/amber semantic labels.
- Iconography is thin-line and technical, used as supporting cues rather than as large illustration. Lucide-like icons appear in navigation, filters, configuration rows, and timeline markers.

## 6. Charts and annotations

- Equity charts use a bright blue line on a dark navy plotting area, with faint horizontal gridlines, subdued axis labels, and a translucent blue area beneath the line (`atlas-overview-page.png`, `atlas-experiments-detail-page.png`).
- Drawdown uses a red line and translucent red filled area below the zero line, making adverse movement immediately legible (`atlas-experiments-detail-page.png`).
- Chart controls are compact: period selector, percent/currency toggle where applicable, and an expand affordance. Controls sit inside the chart panel rather than becoming a separate toolbar.
- The trade chart is a dark candlestick view with green/red candles, a blue EMA line, and horizontal dashed entry/target/stop levels. Labels and price markers use the corresponding semantic colors (`atlas-journal-detail-page.png`).
- Trade annotations are explicit but bounded: Reference, Sweep, Confirmation, Entry, Exit, Target, and Stop. They use small colored labels/markers and do not turn the chart into a dense terminal.
- The screenshots establish treatment and role, not exact chart-library configuration: grid opacity, candle colors, tooltip/crosshair behavior, axis formatting, and responsive chart sizing remain unspecified.

## 7. Semantic state patterns

- PAPER is always visibly identified in the shell as a blue outlined badge; OANDA Practice and a green Connected indicator sit beside it. The visual hierarchy makes environment and connection state persistent without dominating healthy screens.
- Healthy/running/approved/positive states use green dots, text, badges, or values. Examples include Connected, Running, Active, Coverage Verified, Risk approved, BUY/Long, positive P&L, and positive R multiples.
- Negative/risk/stop/short states use red values or controls. Examples include drawdown, negative P&L/R, SELL, Initial Risk/Stop, and the deployment Stop action.
- Warnings use amber rather than red when the condition is informative rather than immediately destructive, such as “Different Strategy Version.”
- Completed experiments use outlined blue `COMPLETED` badges, separating lifecycle state from performance semantics.
- The screenshots show persistent status inline in the relevant panel or row; no evidence suggests relying on transient toast-only communication. This agrees with `context/design/design.md` §Safety States / Sonner.
- The visual language distinguishes source and event types with icon/color combinations in Journal and Recent Activity, while the textual label remains present; color is not the sole carrier of meaning.

## 8. Dark-first versus legacy light-first prose

The current approved V2 mockups are unambiguously **dark-first**. All ten approved PNGs use a deep blue-black app background and dark raised surfaces as the default canvas; text, borders, blue actions, and semantic colors are designed for that dark context. This directly confirms the selected workstream constraint in `dispatch/workstreams/ui-tokens-screenshot-references/PLAN.md` line 6.

The contrary wording in `context/design/design.md` line 25 (“Light/restrained neutral theme preferred”) and the existing near-white frontend token noted in the retained `dispatch/workstreams/ui-tokens-screenshot-references/EXPLORATION.md` lines 63–66 are legacy/context evidence, not a description of the approved V2 PNGs. The V2 screenshots resolve the conflict in favor of dark-first. The other design principles in `design.md`—calm, restrained, low-noise, semantic color, horizontal navigation, and selective cards—remain visually compatible with the V2 direction. This report does not infer a light theme, dual-theme requirement, or redesign.

## 9. Material unknowns only

1. Exact color values, contrast ratios, and whether the apparent shades are shared tokens versus composited chart fills are not recoverable reliably by visual inspection.
2. Exact font family/assets, weight mapping, line-height, and letter-spacing are not identified by the PNGs.
3. Responsive breakpoints, minimum supported viewport, overflow behavior, and mobile treatment are not represented by these wide screenshots.
4. Interactive states not captured in the stills—hover, focus, disabled, loading, error, empty, disconnected, and confirmation states—remain unknown.
5. Chart implementation details (library options, annotation interaction, tooltip/crosshair, and accessibility representation) are not specified by the stills.

## Recommendations to the architect

- Treat the ten approved PNGs as authoritative evidence for a calm, dark-first visual system; explicitly reorient the obsolete light-first sentence in the design context.
- Define only recurring semantic roles evidenced here (surface, text, border, primary, positive, negative, warning, and chart annotation roles), avoiding screen-specific token proliferation.
- Validate exact values, typography, contrast, responsive behavior, and unshown state treatments separately before declaring the visual system complete.
