# EXPLORATION — Product Vision Alignment

Scope: read-only exploration to identify exact current statements, authoritative homes, minimal changes, material contradictions, and cross-reference needs for the approved **proprietary, licensed, local-first Atlas Workstation** vision. No audit. No edits to code/context.

## 1. Approved vision (from PLAN.md)

| Element | Required clarity |
| --- | --- |
| Lifecycle | Build → Experiment → PAPER → LIVE → Monitor → Improve |
| Direction | Proprietary, licensed |
| Operation | Local-first, customer-controlled |
| Principles | Strategy-development principles |
| Boundary | Safety-independent future licensing boundary |

## 2. Authoritative homes today

- `context/product/vision.md` — "What Atlas Is", Primary Goal, Target User, Strategy First, Initial Market/Future, Out of Scope, Product Character, Human Oversight, Success. **Primary home for product vision.**
- `context/product/product-principles.md` — 20+ named principles (Strategy First, Same Methodology Everywhere, Reliability Over Features, Workstation Not Generic SaaS, Broker Agnostic, etc.). **Primary home for product principles.**
- `context/roadmap/roadmap.md` — phases + Deferred list (line 67). **Roadmap scope; forbidden to change in this pass.**
- `AGENTS.md` — root authority: line 5 "single-user … Strategy → Experiment → PAPER → LIVE"; line 21 invariants (all safety rules are unconditional).
- `context/architecture/architecture.md` line 5 — **duplicates** the lifecycle + "workstation" framing (cross-reference risk, see §5).
- `context/design/design.md` line 5 — "workstation — not a generic SaaS dashboard" (consistent, reference-only).
- `context/features/*.md` — no licensing/local-first statements; strategy-management.md line 49 rejects "multi-user sharing"; experiment-comparison.md line 37 rejects "proprietary composite score" (unrelated to licensing). No direct-referencing contradiction.

## 3. Exact current statements vs. approved vision

### 3a. Proprietary / Licensed direction
- **Absent everywhere.** No document states proprietary, licensed, or commercial direction; none claims open-source or free. **No contradiction — this is a gap.**
- Confirmed absent via grep across `context/` for `licens|proprietary|open.?source|SaaS|billing|subscription|installer|cloud|commercial`. Only hits are "Not generic SaaS" / "multi-user SaaS" phrasing, which is a product-character statement, not a licensing statement.
- Authoritative home to add: `context/product/vision.md`.

### 3b. Local-first / customer-controlled operation
- `vision.md:13` — "Not **initially** multi-user SaaS." Consistent in substance but **softened by "initially"**; does not state local-first or customer-controlled operation.
- `AGENTS.md:5` — "single-user" (consistent).
- `product-principles.md:71-73` — "Workstation, Not Generic SaaS" (consistent).
- `roadmap.md:67` — "multi-user SaaS" deferred (consistent with single-user; must not change).
- **No contradiction — gap in explicitness.** "Local-first" and "customer-controlled operation" are not stated anywhere. Authoritative home to add: `context/product/vision.md`. Hardening "Not **initially** multi-user SaaS" to a definitive local-first/customer-controlled statement is the minimal fix.

### 3c. Safety-independent future licensing boundary
- **Absent everywhere.** No principle connects any future licensing/commercial arrangement to capital-safety guarantees.
- Existing safety principles are **unconditional** (`AGENTS.md:21` invariants; `product-principles.md` Explicit Failure, Protect Existing Exposure, Broker Truth Wins) — so nothing currently makes safety contingent on licensing. **No contradiction — new principle to add.**
- Authoritative home to add: `context/product/product-principles.md` (a principle, not vision). Key wording intent: future licensing/commercialization must never condition or weaken capital-safety, correctness, or fail-closed behavior.

### 3d. Lifecycle terminology — **MATERIAL CONTRADICTION**
- `vision.md:5` — "Core lifecycle: **Build → Test → Deploy → Monitor → Improve**."
- `product-principles.md:5` — "easier to **Build → Test → Deploy → Monitor → Improve**."
- `architecture.md:5` — "one core lifecycle: **Build → Test → Deploy → Monitor → Improve**."
- `AGENTS.md:5` — "**Strategy → Experiment → PAPER → LIVE**" (canonical domain framing; different axis).
- Approved: "**Build → Experiment → PAPER → LIVE → Monitor → Improve**."
- Conflict: "**Test**" vs canonical "**Experiment**", and "**Deploy**" vs canonical "**PAPER → LIVE**". `AGENTS.md:17` mandates "A historical backtest is an **Experiment**" and forbids BacktestRun/BacktestResult terminology — "Test" is non-canonical. This is the primary terminology misalignment to fix in the three files above (not AGENTS.md, whose axis is Strategy→Experiment→PAPER→LIVE).

### 3e. Strategy-development principles
- Present and consistent: Strategy First (`vision.md:15-17`; `product-principles.md:5-9`), Same Methodology Everywhere, Immutable Evidence. No change needed beyond lifecycle wording.

## 4. Minimal change set (documentation only)

| File | Change |
| --- | --- |
| `context/product/vision.md` | (1) Align lifecycle to **Build → Experiment → PAPER → LIVE → Monitor → Improve**. (2) Add authoritative proprietary/licensed direction statement. (3) Add/confirm local-first + customer-controlled operation; harden "Not **initially** multi-user SaaS". |
| `context/product/product-principles.md` | (1) Align lifecycle (line 5). (2) Add a "Safety-Independent Licensing Boundary" principle making capital-safety unconditional to any future licensing/commercial arrangement. |
| `context/architecture/architecture.md` | Line 5 lifecycle duplicate — update to canonical wording, or replace with a direct reference to `context/product/vision.md` (single authoritative home per decision). |
| `AGENTS.md` | No change required (already single-user, canonical lifecycle axis). Optionally note local-first; not required. |
| `context/roadmap/roadmap.md` | No change (explicitly forbidden by PLAN; deferred "multi-user SaaS" is compatible with single-user local-first). |
| `context/design/design.md`, `context/features/*` | No change (consistent, reference-only). |

## 5. Cross-reference needs

- `context/architecture/architecture.md:5` is the only architecture file duplicating the product lifecycle/workstation framing. It should either adopt the canonical lifecycle or reference `vision.md` — a clear candidate for the "one authoritative home, direct references elsewhere" rule.
- `context/design/design.md:5` and `product-principles.md:71` repeat "not generic SaaS" — consistent with local-first; keep as references, do not expand into licensing authority.
- `context/roadmap/roadmap.md:67` "multi-user SaaS" deferred is the only roadmap statement touching multi-user; it is compatible with the approved single-user local-first vision and must remain untouched.
- After edits, the lifecycle should be identical in `vision.md`, `product-principles.md`, and (if kept) `architecture.md`.

## 6. Contradiction summary

1. **Lifecycle terminology conflict (material):** "Build → Test → Deploy → Monitor → Improve" (`vision.md:5`, `product-principles.md:5`, `architecture.md:5`) conflicts with canonical "Experiment"/"PAPER"/"LIVE" and the approved "Build → Experiment → PAPER → LIVE → Monitor → Improve."
2. **Proprietary/licensed direction:** absent (gap, not contradiction) — add to `vision.md`.
3. **Local-first / customer-controlled operation:** only implicit via "Not **initially** multi-user SaaS"; soft/absent (gap) — make explicit and definitive in `vision.md`.
4. **Safety-independent licensing boundary:** absent (gap) — add principle to `product-principles.md`. No existing safety statement is contingent on licensing, so no conflict with current invariants.

## 7. Out of scope (confirmed not to touch)

Application code, roadmap, licensing/SaaS/multi-tenancy/billing/installers/cloud infrastructure/SDK packaging/Phase-6-style commercial work (PLAN constraints 22-23). This pass is documentation alignment only.
