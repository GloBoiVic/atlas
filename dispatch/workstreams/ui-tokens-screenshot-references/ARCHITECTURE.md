# Implementation Blueprint — Atlas V2 UI Tokens and Screenshot References

## Outcome

Produce design context that extracts the recurring visual system in the ten approved Atlas V2 mockups. The result is a dark-first, framework-compatible reference for later Tailwind CSS v4, shadcn/ui, and TradingView Lightweight Charts work.

This work does **not** rebuild screens, choose application behavior, alter mockups, configure frameworks, migrate CSS/components, add dependencies, or establish a new visual direction. Written context continues to govern behavior and scope; the ten PNGs govern approved V2 visual appearance.

## Agreed language

- **Approved V2 mockups — confirmed, high confidence:** the ten `context/design/atlas-*-page.png` files listed below; they are the complete canonical visual-reference set for this workstream.
- **Dark-first — confirmed, high confidence:** deep blue-black canvas, dark navy surfaces, restrained cool-neutral text and borders, and sparse semantic color. It does not mean a dense institutional terminal.
- **Semantic token:** a reusable role named for meaning, not a screen, component, raw color, or framework utility.
- **Visual guide:** evidence-backed usage guidance and screenshot references; it is not a screen specification.
- **Exact value — deferred, high confidence:** a color, font metric, spacing dimension, breakpoint, or chart option that cannot be established reliably from the PNGs alone.

## Documentation deliverables and ownership

| Deliverable | Required change | Owner |
| --- | --- | --- |
| `context/design/ui-tokens.md` | Add the canonical semantic vocabulary, naming rules, role/alias tables, qualitative visual intent, evidence references, and exact-value status. | One assigned design-context writer |
| `context/design/visual-guide.md` | Add the visual hierarchy, recurring patterns, chart treatment, state usage, anti-patterns, and ten-mockup validation matrix. | Same writer, sequentially |
| `context/design/design.md` | Reorient legacy visual wording, link the two new guides and all ten approved PNGs, and remove the deleted composite-screenshot reference. Preserve behavioral and product guidance. | Same writer, last |
| Approval, READY receipt, assignment, and review record | Control the workflow; never delegate these records to the context writer. | Orchestrator |
| Cross-document and visual validation | Read-only review against this blueprint and every approved PNG. | Independent reviewer |

No other context file, mockup, dispatch artifact, or application file is a documentation deliverable.

## Decisions

### 1. Authority and legacy reorientation

- The approved V2 mockups are dark-first and supersede only the obsolete light-first visual preference in `design.md`. Preserve its calm, restrained, technical, low-noise principles and all behavior/scope rules.
- Replace “Light/restrained neutral theme preferred” with dark-first wording that explicitly retains the prohibition on gradients, ornamental shadows, decorative motion, excessive semantic color, dense terminal styling, and dashboard tile walls.
- In `design.md`'s mockup section, list or link the ten individual PNGs as the approved set. Remove the stale reference and handling instruction for deleted `context/design/screenshot/atlas-screens.PNG`; do not recreate it.
- State the precedence precisely: written context governs behavior and scope; approved PNGs govern V2 appearance; `ui-tokens.md` and `visual-guide.md` interpret recurring visual evidence without overriding either.
- Screenshot-only differences such as the absent Data navigation item or visible search control do not authorize navigation or behavior changes.

### 2. Semantic token scope and naming

Canonical documentation identifiers use `atlas.<category>.<role>`. A later CSS implementation may normalize them to `--atlas-<category>-<role>`; framework aliases are adapters, not new source tokens.

**Core color roles:**

- `atlas.color.background`: application canvas.
- `atlas.color.surface`: panels, cards, tables, filter strips, and controls.
- `atlas.color.border`: hairlines, dividers, and control outlines.
- `atlas.color.foreground`: primary text and key neutral values.
- `atlas.color.foreground-muted`: labels, supporting copy, timestamps, axes, and secondary navigation.
- `atlas.color.primary` / `atlas.color.primary-foreground`: selected state, primary action, information, links, and active rules.
- `atlas.color.positive` / `atlas.color.positive-foreground`: healthy, connected, running, long, and favorable values.
- `atlas.color.negative` / `atlas.color.negative-foreground`: critical, stop, short, loss, and adverse values.
- `atlas.color.warning` / `atlas.color.warning-foreground`: informative mismatch or caution that is not critical.
- `atlas.color.focus-ring`: keyboard focus; may alias primary only after contrast validation.

Do not add separate page, component, lifecycle, PAPER, LIVE, badge, or control colors where these roles compose correctly. PAPER and completed lifecycle state use primary treatment; LIVE remains a semantic environment distinction whose exact treatment is deferred until LIVE design exists.

**Supporting recurring roles:**

- Type: `atlas.type.page-title`, `section-title`, `body`, `label`, `metadata`, `metric`, and `helper`.
- Layout: `atlas.layout.content-max`, `page-gutter`, `section-gap`, `panel-padding`, `control-height`, and `table-row-height`.
- Shape: `atlas.radius.panel`, `control`, and `badge`; `atlas.border.hairline-width`.

These names document hierarchy and reuse. Exact font family, weights, sizes, line heights, tracking, dimensions, and radii remain deferred; approximate screenshot measurements must not become normative values.

**Chart roles are aliases, not an independent palette:**

- Equity, EMA, and entry map to primary.
- Drawdown, down candles, and stop map to negative.
- Up candles, target, and exit map to positive.
- Grid maps to border; axes map to muted foreground; chart canvas maps to background/surface.
- Confirmation maps to warning; reference maps to muted foreground.
- Sweep's violet treatment is documented as a chart-local annotation observed only in `atlas-journal-detail-page.png`, not promoted to a global token without recurring evidence.

The token guide must show future adapter examples conceptually: Tailwind v4 `@theme` `--color-atlas-*` aliases and shadcn-compatible `background`, `foreground`, `card`, `primary`, `destructive`, `border`, `input`, and `ring` aliases may point to Atlas roles. It must not prescribe or edit CSS. Existing `--atlas-background`, `--atlas-ink`, `--color-atlas-blue`, and ad hoc utility colors are later migration inputs, not authoritative V2 values.

### 3. Visual-guide structure

`visual-guide.md` must contain, in order:

1. Authority, scope, and dark-first character.
2. Approved screenshot inventory with all ten exact paths.
3. Global shell, horizontal navigation, content width, gutters, and page-header hierarchy.
4. Typography and financial-number hierarchy.
5. Color semantics, environment/connection presentation, and color-not-as-sole-signal rule.
6. Surfaces, borders, radii, spacing rhythm, and explicit no-gradient/no-ornamental-shadow guidance.
7. Recurring patterns: page headers, selective panels, tables, filters, tabs, forms, buttons, badges, dots, and activity/timeline rows.
8. TradingView chart treatment: canvas, grid, axes, series, candles, levels, labels, and bounded annotations.
9. Persistent safety/state communication, accessibility expectations, and unknown interactive/responsive states.
10. Anti-patterns and migration boundaries.
11. Per-mockup validation matrix covering shell, hierarchy, patterns, semantics, and chart evidence where present.

The guide may describe repeated composition but must not encode page-specific spacing, copy, data, or component tokens.

## Constraints, risks, and deferred values

- **Exact visual values — deferred, high confidence:** PNG inspection supports roles and approximate appearance, not authoritative hex/OKLCH values, contrast ratios, typography metrics, spacing, radii, breakpoints, or chart opacity/options. Label approximations as non-normative evidence or omit them.
- **Unshown states — deferred, high confidence:** hover, focus, disabled, loading, error, empty, disconnected, narrow-screen, tooltip, crosshair, and annotation interaction require later accessibility and implementation validation.
- **Over-tokenization risk — confirmed, high confidence:** admit a core token only when recurring across mockups or existing cross-screen conventions. Keep one-off treatment in the visual guide.
- **Dark terminal drift — confirmed, high confidence:** dark surfaces must remain spacious and restrained; do not add glow, gradients, decorative shadows, dense controls, or excessive green/red.
- **Accessibility and safety:** color always accompanies text, icon, shape, or position. Persistent safety conditions remain persistent. Exact foreground pairs and focus treatment require WCAG contrast checks before application migration.
- **Security/data:** documentation and approved static assets contain no credential path or runtime data contract. Do not introduce secrets, external assets, or fabricated trading behavior.
- **Rollback:** documentation-only changes can be reverted as one scoped unit. There is no database, API, dependency, or runtime migration.

## Migration boundaries

This workstream migrates design context only. It may add the two guides and update `design.md`; it must not touch `frontend/`, Tailwind configuration/CSS, shadcn setup/components, chart code/options, dependencies, mockup files, or product/feature/architecture context.

Application adoption is a separate approved workstream. That later work must inventory current CSS/component usage, select and contrast-test exact values, map Atlas roles to Tailwind/shadcn aliases, theme Lightweight Charts, migrate incrementally, and visually regress existing screens. It must not infer implementation authorization from this blueprint.

## Ordered sequential implementation

1. **Explicit approval gate:** the developer approves this blueprint and the proposed documentation-only workflow. Disagreement requires blueprint revision and re-approval; approval is not Git authorization.
2. **Post-approval READY isolation gate:** invoke the `worktrees` workflow and obtain operation-specific confirmation before repository-changing Git commands. Record a `READY` receipt with mode, repository root, assigned cwd `/Users/vike/Desktop/atlas`, working path, branch, full SHA, scope, clean/known status, loaded context, recovery, and allowed files. Required isolation scope is only `context/design/design.md`, `context/design/ui-tokens.md`, and `context/design/visual-guide.md`. No writer starts before READY.
3. **Write token guide:** create `ui-tokens.md` using only the roles, naming rules, aliases, evidence, and deferred-value boundaries above.
4. **Write visual guide:** create `visual-guide.md` in the mandated section order; cite recurring evidence and complete all ten matrix rows.
5. **Reorient entry context:** update `design.md` narrowly: establish dark-first V2 appearance, link the guides and ten PNGs, and remove the deleted composite reference. Do not rewrite unrelated guidance.
6. **Validate:** one independent reviewer compares all three documentation deliverables with this blueprint, `design.md`, and each PNG. Material conflict returns to the orchestrator; the reviewer or writer must not silently change architecture.
7. **Close:** report scoped diffs and validation results. No automatic commit, push, merge, cleanup, application migration, or follow-on implementation is authorized.

## Validation and acceptance criteria

- Only the three allowed context-design paths are changed by the documentation writer.
- `design.md` is unambiguously dark-first while retaining calm/low-noise behavior and scope guidance.
- No reference to `context/design/screenshot/atlas-screens.PNG` remains, and the deleted file is not recreated.
- Both new guides are linked from `design.md`; all ten approved paths appear exactly once in the canonical inventory and each has a completed validation-matrix row:
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
- Every core token is semantic and supported by recurring evidence; aliases do not create duplicate source values; one-off visual treatments are not promoted to global tokens.
- Approximate observations and deferred exact values are clearly distinguished from normative decisions.
- The guides support later Tailwind v4, shadcn/ui, and Lightweight Charts mapping without containing implementation code or requiring a dependency/configuration change.
- No screen layout, navigation behavior, trading behavior, canonical terminology, safety rule, mockup, or application style is changed by this workstream.
- Review explicitly records pass/fail for cross-document consistency, all ten visual comparisons, token restraint, accessibility caveats, migration boundaries, and stale-reference removal.

Blueprint ready.
