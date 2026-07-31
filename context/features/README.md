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

## Implementation Order

`context/roadmap.md` owns the canonical implementation sequence. Feature files retain stable domain IDs, so their numeric order is not necessarily their delivery order. Feature dependencies must refer to the domain feature they require and must not create cycles.
