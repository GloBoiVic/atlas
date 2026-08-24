# VALIDATION — UI Tokens + Screenshot References

- **Validator:** `tester` / `opencode/deepseek-v4-flash`
- **Date:** 2026-08-23
- **Assigned artifact:** this `VALIDATION.md`
- **Scope:** Read-only, independent validation of the three completed design-context deliverables against the authoritative blueprint (`ARCHITECTURE.md`, `PLAN.md`, `READY.md`, `TASK-1.md`, `design.md` precedent, and all ten approved V2 PNGs). No application code, mockup, dispatch artifact, or Git state was changed.

## Method note — visual evidence

The assigned model (`deepseek-v4-flash`) does **not** support image input (verified: `Read` of a PNG returned "Cannot read image (this model does not support image input)"). This is the same capability blocker recorded in `PLAN.md` for the original explorer. To still independently corroborate the screenshots against the stated recurring evidence, I decoded each PNG in pure Python (`zlib` + PNG filter reconstruction) and ran two deterministic pixel analyses: (1) overall luminance / top-quantized-palette, and (2) a hue classifier for semantic color sparsity and per-mockup color presence. This is programmatic visual evidence, not human-grade pixel review; direct pixel-level inspection by a capable reviewer remains advisable at review. The dark-first character and all semantic-color claims below are corroborated numerically; no exact visual judgment (type metrics, radii) was asserted.

---

## Criterion-by-criterion results

### 1. Only allowed source paths changed (accounting for inherited dirty state) — **PASS**

- `git status --short -- context/design/` shows the writer's changes confined to the three authorized paths:
  - `M  context/design/design.md`
  - `?? context/design/ui-tokens.md`
  - `?? context/design/visual-guide.md`
- The ten PNGs are untracked **inputs** (mtime 22:34–22:36, before the writer's writes at 23:14); not modified by the writer.
- `D  context/design/screenshot/atlas-screens.PNG` is the **inherited** dirty state preserved per `READY.md` ("inherited dirty working tree; no cleanup, reset, or other Git mutation performed"), not a writer action; it is absent from the allowed scope and was not recreated.
- Pre-existing dirty paths (`backend/*`, `frontend/*`, `dispatch/ACTIVE.md`, `dispatch/COMPLETED.md`, `memory.md`, `phase-6-strategy-iteration/`) are outside this documentation workstream and unchanged by it.
- `TASK-1.md`'s own "Changed paths" list matches reality: three design paths + the required task report. No out-of-scope source change found.

### 2. Dark-first reorientation — **PASS**

- `git diff HEAD -- context/design/design.md` shows exactly two hunks, both in-scope:
  - *Visual Character*: replaced "Light/restrained neutral theme preferred" with "Approved V2 appearance is dark-first: deep blue-black canvas, dark navy surfaces, cool-neutral text and borders, and sparse semantic color. This is not a dense institutional terminal." — explicitly retains the prohibitions on excessive green/red, dense walls, oversized KPI dashboards, gradients, **ornamental shadows**, and decorative animations.
  - *Responsive / Mockups / Screenshot*: replaced the composite-screenshot paragraph with the ten-PNG approved set and a precedence statement.
- Pixel corroboration: every one of the ten PNGs has average luminance 13.3–21.6 and <2.0% bright pixels; dominant top-quantized colors are deep blue-black (`#000018`, `#001818`, `#000000`) and dark navy (`#181830`, `#001830`). The reorientation reflects the actual approved screens.
- Behavioral/product/navigation/safety sections were untouched (see criterion 8).

### 3. No stale composite reference / no recreation — **PASS**

- `grep -rn "atlas-screens\|screenshot/atlas\|composite"` across `design.md`, `ui-tokens.md`, `visual-guide.md` → **no matches**.
- `test -e context/design/screenshot/atlas-screens.PNG` → absent (not recreated).
- `git diff HEAD -- design.md` confirms the "Existing composite screenshot: `context/design/screenshot/atlas-screens.PNG` (1536×1024 composite). Do not split, rename, or move it…" sentence and its handling instruction were removed.

### 4. Bidirectional guide links — **PASS**

- `design.md` → both guides: `` [`ui-tokens.md`](ui-tokens.md) `` and `` [`visual-guide.md`](visual-guide.md) `` (Visual Character section) — both resolve to files present in the same directory.
- `visual-guide.md` → `ui-tokens.md` (lines 6, 53, 103).
- `ui-tokens.md` → `visual-guide.md` (lines 9, 97).
- All four link directions present; no broken relative links.

### 5. Exactly ten canonical inventory entries + ten completed matrix rows — **PASS**

- `visual-guide.md` §2 "Approved screenshot inventory" lists the exact ten `context/design/atlas-*-page.png` paths, each appearing **exactly once** (verified programmatically: count = 1 per path in `visual-guide.md` and 1 in `design.md`).
- §11 "Per-mockup validation matrix" has a header (line 131), separator (132), and **exactly ten completed data rows** (lines 133–142), one per inventory entry, each filling Shell/hierarchy, Recurring patterns, Semantic evidence, and Chart evidence columns.
- The ten inventory paths exactly match the ten approved files present on disk and the ten required in `ARCHITECTURE.md` acceptance list; order matches.

### 6. Semantic token restraint and deferred exact values — **PASS**

- `ui-tokens.md` documents exactly the blueprint's token set — core color roles (background, surface, border, foreground, foreground-muted, primary/primary-foreground, positive/positive-foreground, negative/negative-foreground, warning/warning-foreground, focus-ring) plus type (7), layout (6), and shape (4) roles — **no** page-, component-, badge-, lifecycle-, PAPER-, or LIVE-specific colors added. The chart mapping is a role-alias table, not an independent palette.
- One-off treatments correctly confined to the guide: Sweep's violet is "a chart-local annotation … not promoted to a global token without recurring evidence."
- **No hex/OKLCH literals** appear in either guide (`grep -nE '#[0-9a-fA-F]{3,8}'` → no matches); every exact value is marked deferred ("exact value deferred", "contrast-tested value deferred"). Approximate screenshot measurements are explicitly labeled non-normative evidence.
- Naming rule `atlas.<category>.<role>` used consistently; `--atlas-<category>-<role>` and shadcn aliases are described as adapters, not new source tokens.

### 7. Tailwind/shadcn/Lightweight Charts guidance is conceptual — **PASS**

- `ui-tokens.md` §"Future adapter examples (conceptual only)" describes `@theme --color-atlas-*` and shadcn alias mapping as **mapping examples, not CSS instructions or new source values**; it references `--atlas-background`, `--atlas-ink`, `--color-atlas-blue` as migration inputs. No `@media`, CSS rules, `.css` edits, or dependency/config content.
- `visual-guide.md` §8 treats chart treatment conceptually (canvas, grid, axes, series, levels, bounded annotations) and defers opacity/options/tooltip/crosshair/interaction; §10 states it "does not authorize edits to `frontend/`, CSS, Tailwind or shadcn configuration, chart code, dependencies…" and defers application adoption to a separate workstream.
- No framework configuration or implementation code in any deliverable.

### 8. Retained behavior / safety / navigation scope — **PASS**

- `design.md` diff is limited to the Visual Character and Responsive/Mockups sections. All behavioral sections preserved verbatim: Navigation (horizontal, no sidebar), Safety States/Sonner (persistent failures never rely solely on toasts; Sonner transient only), Color/PAPER-vs-LIVE/Connection State, Human-Readable Language/terminology, USD Base Currency, Initial Scope/information density, empty states, detail navigation.
- Both guides carry the precedence statement: written context governs behavior/scope; approved PNGs govern V2 appearance; neither authorizes navigation/behavior changes. The "screenshot-only difference" caveat (absent Data nav item / visible search control) is explicitly stated in `design.md`, `visual-guide.md` §3, §10.
- No canonical terminology introduced (Experiment, not Backtest; no Bot/Worker/etc.); no screen layout or trading behavior claimed.

### 9. All ten screenshots match stated recurring evidence — **PASS (programmatic)**

Per-mockup hue-classification (40k+ samples each; semantic color as % of pixels) vs. the validation-matrix claims:

| Mockup | Matrix claim | Corroboration | Result |
| --- | --- | --- | --- |
| Overview | Blue equity line + subdued grid/area; sparse pos/neg | blue 3.70% (highest of set), green 0.23%, red 0.04%, dark 93.5% | PASS |
| Strategies | Blue selection/action; neutral metadata; not chart-dominant | blue 0.63%, dark 98.2%, no dominant chart fill | PASS |
| Strategy details | Detail title, restrained tabs; not chart-dominant | blue 0.75%, dark 97.5% | PASS |
| Experiments | Bordered filter strip, table, lifecycle badges; completed primary | blue 1.15%, dark 96.7% | PASS |
| Experiment detail | Equity blue; drawdown red w/ restrained fills | red 2.43% (highest red of set — drawdown area), blue 1.89%, dark 93.4% | PASS |
| Experiment run | Chart secondary to run workflow | blue 1.21%, dark 96.1% | PASS |
| Compare experiments | Different Strategy Version uses amber warning | amber/orange pixels present (`#a06020`, `#c08000`, `#a06000`), sparse (~0.06%) — consistent with "informative mismatch" | PASS |
| Deployments | Connected/Running/Active green; Stop red; PAPER explicit; not chart-dominant | green 0.05%, red 0.08%, blue 0.30%, dark 97.9% | PASS |
| Journal | BUY/positive green, SELL/negative red w/ text | green 0.32%, red 0.08%, blue 0.21%, dark 96.4% | PASS |
| Journal detail | Candles, EMA, levels, Reference/Sweep/Confirmation annotations | green 0.54% + red 0.40% + blue 0.65% (candles/EMA/levels) **and violet Sweep pixels present**; amber (`#e04020`, `#c08000`) | PASS |

Cross-set: dark pixel share 93–98% across all ten (dark-first, sparse semantic color) — matches the stated "sparse semantic color" and "not a dense institutional terminal" character. Note: amber/violet are sparse and hue-classified with tuned thresholds; a visual reviewer should confirm the specific amber "Different Strategy Version" label and violet Sweep annotation, but numerical evidence is consistent with the claims.

### 10. Cross-document consistency — **PASS**

- `ui-tokens.md`, `visual-guide.md`, and `design.md` use the same dark-first character language and the same authority/precedence framing; chart roles in `visual-guide.md` §8 map to the roles in `ui-tokens.md`; environment/PAPER treatment consistent (primary treatment; LIVE exact treatment deferred); safety/color-redundancy wording consistent across all three.
- No contradiction found among the deliverables, the blueprint, or `design.md` precedent.

---

## Commands / checks run

```
# Scope & inherited dirty state
git status --short
git status --short -- context/design/

# Screenshot presence + stale-file absence
test -e context/design/screenshot/atlas-screens.PNG            # absent (good)
ls -la context/design/                                        # ten PNGs, mtimes pre-write

# Reorientation + stale-reference removal
git diff HEAD -- context/design/design.md
grep -rn "atlas-screens\|screenshot/atlas\|composite" context/design/design.md ui-tokens.md visual-guide.md

# Canonical inventory exactness + matrix rows (python)
#   per-path count in visual-guide.md and design.md; total distinct = 10
grep -nE '^\|' context/design/visual-guide.md                  # 10 data rows (133-142)

# Bidirectional links
grep -oE '\[`[a-z-]+\.md`\]\([a-z-]+\.md\)' context/design/design.md
grep -n "ui-tokens.md" context/design/visual-guide.md
grep -n "visual-guide.md" context/design/ui-tokens.md

# Token restraint + deferred values + conceptual-only guidance
grep -oE 'atlas\.[a-z]+\.[a-z-]+' context/design/ui-tokens.md | sort -u
grep -nE '#[0-9a-fA-F]{3,8}\b' context/design/ui-tokens.md visual-guide.md   # no hex
grep -nE '@theme|--atlas-|shadcn|@media|\.css' context/design/ui-tokens.md

# Programmatic visual corroboration (pure-python PNG decode)
python3 /tmp/atlas_png_analyze.py      # luminance + top palette per mockup
python3 /tmp/atlas_hue.py              # semantic-color sparsity per mockup
python3 /tmp/atlas_probe.py            # amber (compare) + violet (journal-detail)
```

## Overall verdict

**PASS** — all ten acceptance criteria validated, cross-document consistent, screenshot evidence numerically corroborated, no material discrepancies found. The three completed deliverables faithfully realize the authoritative blueprint without out-of-scope changes.

**Material discrepancies:** none.

**Minor observations (non-blocking):**
1. Direct pixel-level human/visual review is still recommended given the validator's image-input limitation; numerical evidence is strongly consistent but not a substitute for human-grade inspection of typography, radii, and the amber "Different Strategy Version" label / violet Sweep annotation.
2. `design.md`'s guide links use backtick-wrapped text inside link text (`` [`ui-tokens.md`](ui-tokens.md) ``) — valid Markdown, renders correctly, not a defect.
