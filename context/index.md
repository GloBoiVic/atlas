# Context Index

Read root `AGENTS.md` first, then load only task-relevant documentation.

## Core
- **architecture/** — architecture, domain, safety, runtime, data, persistence, and repository conventions.
- **product/** — product vision and principles.
- **roadmap/** — phased delivery scope and exit criteria.
- **features/** — feature-level requirements and boundaries.
- **development/** — engineering standards, skills, and workflow guidance.

## Optional
- **design/** — UI design specification and visual references.

## Authority map

- **Domain language and invariants:** `../AGENTS.md`, `architecture/domain-model.md`
- **Strategy behavior and boundary:** `architecture/strategy-contract.md`, `features/reference-strategy.md`
- **Market-data truth:** `architecture/market-data-model.md`, `features/historical-data.md`
- **Experiment semantics:** `features/experiments.md`, `architecture/accounting-model.md`
- **Runtime and safety:** `architecture/runtime-model.md`, `architecture/safety-model.md`
- **Product direction and delivery:** `product/vision.md`, `product/product-principles.md`, `roadmap/roadmap.md`
- **Current repository status:** `../CURRENT.md`; setup/use: `../README.md`

When documents conflict, use the more specific authority above and report stale
historical text rather than treating it as a current contract.

## Missing (reported, not scaffolded)
- **None identified.**
