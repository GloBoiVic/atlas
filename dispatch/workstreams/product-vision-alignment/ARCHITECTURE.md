# ARCHITECTURE — Product Vision Alignment

## Implementation Blueprint — Product Vision Alignment

### Outcome

Align three authoritative context documents with the approved Atlas Workstation direction using the smallest documentation-only change set:

- `context/product/vision.md` owns the product lifecycle, proprietary/licensed direction, and local-first/customer-controlled operating model.
- `context/product/product-principles.md` owns the principles that guide Strategy development and establishes the safety-independent boundary for any future licensing mechanism.
- `context/architecture/architecture.md` references the product lifecycle in `vision.md` instead of restating it.

This work does not change application behavior, architecture, the roadmap, or current delivery scope. It does not authorize or design licensing enforcement, billing, SaaS, multi-tenancy, installers, cloud services, SDK packaging, commercial operations, or an alignment audit.

### Agreed language

- **Canonical product lifecycle** (**confirmed**, high confidence): **Build → Experiment → PAPER → LIVE → Monitor → Improve**. `context/product/vision.md` is its authoritative home.
- **Proprietary, licensed direction** (**confirmed**, high confidence): Atlas is intended to be proprietary software distributed under a license. This is product direction only, not approval to implement commercial or license-control infrastructure.
- **Local-first** (**confirmed**, high confidence): Atlas's application, runtime, and durable product state operate under the customer's control. This does not imply offline-only operation; broker and market-data integrations remain external dependencies.
- **Customer-controlled operation** (**confirmed**, high confidence): the customer controls the workstation and trading activation while retaining the human oversight already required by Atlas. It does not introduce users, tenancy, or hosted-operation requirements.
- **Safety-independent licensing boundary** (**confirmed**, high confidence): any future licensing or commercial mechanism remains outside the capital-safety path. It may never weaken correctness, fail-closed behavior, broker-hosted protection, reconciliation, visibility of existing exposure, or safe risk-reducing actions.
- **Strategy-development principles** (**confirmed**, high confidence): Strategy First, Same Methodology Everywhere, deterministic and explainable behavior, immutable evidence, centralized Risk, and completed-data-only evaluation remain the governing principles. No new Strategy framework is introduced.

### Decisions

- **One owner per decision**: put product identity, operating model, commercial direction, and the canonical lifecycle in `vision.md`; put behavioral principles in `product-principles.md`; keep architecture focused on system structure. This follows the existing “define once, link elsewhere” documentation principle.
- **Replace, do not append to, obsolete lifecycle language**: remove every in-scope use of **Build → Test → Deploy → Monitor → Improve**. Do not retain the old phrase as an alias because `Experiment`, `PAPER`, and `LIVE` are canonical Atlas terms.
- **Architecture uses a direct reference**: revise `context/architecture/architecture.md` Purpose to link to `../product/vision.md` for the product lifecycle, while retaining the architectural statement that one StrategyVersion moves through Experiment → PAPER → LIVE without methodology changes. Do not make architecture a second lifecycle authority.
- **Product principles reference the lifecycle owner**: revise “Strategy First” to link to the lifecycle in `vision.md` and state its implementation consequence rather than defining a second lifecycle. Keep “Same Methodology Everywhere” as the concise Strategy boundary principle.
- **Commercial direction is declarative, not operational**: state proprietary/licensed direction in `vision.md` without license types, pricing, entitlement behavior, telemetry, hosting, distribution, or enforcement design.
- **Local-first is not offline-only**: describe customer control without contradicting OANDA, market-data, or broker authority boundaries.
- **Licensing cannot compromise safety**: add one concise principle to `product-principles.md`. A future invalid or unavailable entitlement may be designed to block activation or new exposure safely, but must not strand or conceal existing exposure or prevent protection, reconciliation, and safe risk reduction. This establishes a future boundary only; it creates no current implementation task.
- **Preserve roadmap authority**: make no edit to `context/roadmap/roadmap.md`. Product direction must not promote deferred work or alter any phase, Golden Path, exit criterion, or “Do Not Build” list.

### Constraints and risks

- **Scope expansion risk**: words such as “licensed” and “local-first” could be mistaken for current deliverables. Pair them with explicit future-direction/no-current-infrastructure wording.
- **Safety ambiguity risk**: do not imply that licensing can stop protection or other risk-reducing behavior for open exposure. Safety invariants remain unconditional.
- **Authority drift risk**: do not copy a long-form vision into principles or architecture. Use relative Markdown links to the authoritative product document.
- **Terminology risk**: preserve canonical `StrategyVersion`, `Experiment`, `PAPER`, `LIVE`, `Deployment`, and `Risk` capitalization and meanings. Do not introduce Backtest, Bot, or environment-specific Strategy concepts.
- **Product-character risk**: “local-first” must not be rewritten as generic SaaS or cloud-hosted direction. Existing single-user/workstation scope remains intact.
- **Roadmap risk**: no roadmap or feature file may change, including the deferred multi-user SaaS entry.
- **Security and privacy**: documentation must not prescribe credential transport, license keys, telemetry, remote validation, or customer-data collection. Those require separate approved architecture work if ever requested.
- **Migration and rollback**: no data, API, schema, or runtime migration exists. Rollback is a documentation revert limited to the three context files in this blueprint.
- **Isolation scope** (**assumed**, high confidence): assigned cwd is `/Users/vike/Desktop/atlas`; the implementation writer may edit only the three listed context files plus its assigned dispatch artifact. Git isolation and repository-changing Git commands require separate workflow authorization.

### Ordered implementation

1. **Make product vision authoritative** — edit `context/product/vision.md` only where needed:
   - Replace the lifecycle in “What Atlas Is” with **Build → Experiment → PAPER → LIVE → Monitor → Improve**.
   - State that Atlas is a proprietary, licensed, local-first workstation operated under customer control.
   - Clarify the operating model without promising offline-only behavior or changing external broker/provider dependencies.
   - Harden “Not initially multi-user SaaS” so it cannot imply that SaaS is part of current scope; retain the existing single independent trader target.
   - Align the “Success” lifecycle wording by referring back to the canonical lifecycle rather than preserving build/test/deploy terminology.
   - Keep initial market, out-of-scope list, human oversight, and all trading-methodology statements substantively unchanged.

2. **Align product principles without duplicating vision** — edit `context/product/product-principles.md`:
   - In “Strategy First,” link directly to `vision.md` as lifecycle authority and retain the rule that secondary infrastructure must not become the product.
   - Leave existing Strategy-development and trading-safety principles intact.
   - Add one “Safety-Independent Licensing Boundary” principle near the existing safety principles. State the unconditional boundary and explicitly preserve protection, reconciliation, exposure visibility, fail-closed handling, and safe risk reduction.
   - Mark licensing as a future concern; do not describe commercial implementation.

3. **Remove architecture duplication** — edit `context/architecture/architecture.md`:
   - In “Purpose,” replace the duplicated lifecycle phrase with a direct relative link to `../product/vision.md`.
   - Retain the same-StrategyVersion Experiment → PAPER → LIVE architectural consequence.
   - Make no other architecture change.

4. **Validate the documentation-only boundary**:
   - Review the final diff and confirm only the three approved context files changed for product alignment.
   - Confirm roadmap, feature specifications, source code, schemas, dependencies, and configuration are untouched.
   - Record validation in the workstream's assigned validation artifact; do not broaden into an alignment audit.

### Validation

- `vision.md` contains the canonical lifecycle exactly and no longer contains **Build → Test → Deploy → Monitor → Improve** or an equivalent Test/Deploy lifecycle.
- `product-principles.md` links to `vision.md` for lifecycle authority, preserves current Strategy principles, and contains one concise safety-independent licensing principle.
- `architecture.md` directly links to `../product/vision.md` for lifecycle authority and does not restate either lifecycle phrase.
- Product direction clearly says proprietary, licensed, local-first, and customer-controlled while explicitly avoiding present implementation commitments.
- Licensing language cannot reasonably be read to weaken protection, reconciliation, fail-closed behavior, exposure visibility, or risk-reducing actions.
- `context/roadmap/roadmap.md` and all application/code/configuration files are unchanged.
- Existing current-scope statements remain: single-user workstation, EUR/USD/OANDA initial slice, StrategyVersion methodology continuity, roadmap phases, and deferred work.
- Markdown headings and relative links resolve; terminology matches `context/architecture/domain-model.md`.
- No audit findings, commercial design, acceptance of roadmap expansion, or implementation tasks are introduced.

Blueprint ready.
