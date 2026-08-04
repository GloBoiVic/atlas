# Atlas — Feature Files

This directory contains individual feature specifications for Atlas. Each feature is a vertical slice that can be implemented, tested, and verified independently. The roadmap owns delivery order; these files retain stable domain IDs.

## How to Use

1. **Before implementing:** Read the feature file, the architecture context file, and the relevant parts of the tech stack.
2. **Implement only the current feature.** Do not implement future features.
3. **Follow the acceptance criteria.** Each feature has clear "Done when" criteria.
4. **Update the file** to mark deliverables as complete (`[x]` instead of `[ ]`).

## Feature File Template

Each feature file follows this structure:

```markdown
# Feature: [Feature Name]

## Description
[What this feature does and why it exists]

## User Stories
- As a [user], I want [action] so that [benefit]

## Dependencies
- [Other features or components this depends on]

## Deliverables
- [ ] [Specific deliverable 1]
- [ ] [Specific deliverable 2]
- [ ] ...

## Technical Details
[Implementation specifics — interfaces, models, patterns]

## Acceptance Criteria
- [ ] [Criterion 1]
- [ ] [Criterion 2]
- [ ] ...

## Done when
- [All acceptance criteria are met]
- [All tests pass]
- [Linting and type checking pass]
```

## Feature ID to Roadmap Phase Mapping

Feature IDs are stable domain identifiers, not delivery-order numbers. The roadmap owns the canonical implementation sequence. Below is the authoritative mapping:

| Feature ID | Domain feature | Roadmap phase(s) |
|---|---|---:|---|
| 02 | Core Infrastructure | Phase 2 |
| 03 | Data Layer | Phase 3 |
| 04 | Strategy Engine | Phase 4 |
| 05 | Backtesting | Phase 7 |
| 06 | Risk Engine | Phase 5 |
| 07 | Execution Layer | Phase 6 |
| 08 | Live Data Streaming | Phases 3 and 8 |
| 09 | Live Trading (Paper + Testnet) | Phases 8 and 11 |
| 10 | Journal & Analytics | Phase 9 |
| 11 | UI Dashboard & Core Pages | Phase 10 |
| 12 | Bot Management | Phases 8 and 10 |
| 13 | Polish & Testing | Phase 12 |

See `context/roadmap.md` for the full delivery sequence and dependency gates.

## Implementation Order

`context/roadmap.md` owns the canonical implementation sequence. Feature files retain stable domain IDs, so their numeric order is not necessarily their delivery order. Feature dependencies must refer to the domain feature they require and must not create cycles.
