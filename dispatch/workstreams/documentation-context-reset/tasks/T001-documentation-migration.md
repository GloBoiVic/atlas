# T001 — Documentation and Context Migration

## Assignment

- **Role:** `BUILD`
- **Workstream:** `documentation-context-reset`
- **Branch:** `solo/documentation-context-reset`
- **CWD:** `/Users/vike/Desktop/atlas-documentation-context-reset`
- **State:** `DONE`
- **Owned artifact:** this task file
- **Specialist skills:** none

## Objective

Implement the approved documentation/context reset from the clean committed-main
baseline. Use `dispatch/workstreams/documentation-context-reset/PLAN.md` as the
complete authority for the exact inventory and merge map.

## Allowed changes

- Rewrite `AGENTS.md` to the approved concise routing/authority document,
  target ≤100 lines.
- Rewrite `README.md` to the approved current capability/setup/workflow/
  validation document.
- Add `DOMAIN.md` with only the approved durable cross-cutting laws, target
  ≤120 lines.
- Delete exactly the approved `CURRENT.md`, `memory.md`, all listed
  `context/**` files/assets, and approved empty root `dispatch/*.md`
  placeholders, subject to the dependency stop rule.

## Required preservation

- Do not edit `dispatch/ACTIVE.md`; it belongs to the separate `paper-01`
  workstream.
- Do not edit `dispatch/COMPLETED.md`, `dispatch/MODEL-LOG.md`, historical
  root phase records, or any existing `dispatch/workstreams/**` artifact.
- Do not read unfinished PAPER implementation as permanent-context authority.
  Use committed `main` evidence only for current capability claims.
- Do not change application code, tests, fixtures, schemas, migrations,
  generated clients, frontend behavior, configuration, dependencies, secrets,
  or Git history.

## Stop conditions

Stop without improvising and report `BLOCKED` if any planned deletion has a real
tooling or workflow dependency, including a code/build/import reference, a
required dispatch workflow reference, or a non-historical runtime contract.
Do not resolve a dependency by creating a replacement documentation tree,
ADR, archive, or legacy directory.

## Completion checks

Before marking `DONE`, independently check:

1. `AGENTS.md` is ≤100 lines and `DOMAIN.md` is ≤120 lines.
2. Current/root authority docs do not refer to deleted `context/` or
   `CURRENT.md`/`memory.md` paths. Historical dispatch records may retain old
   references and must remain unchanged.
3. README commands match the committed-main manifests and source tree; no
   unfinished PAPER capability is claimed as current.
4. Each DOMAIN law is supported by committed-main implementation/tests or is
   explicitly stated as a future safety boundary rather than an implementation
   claim.
5. `git diff --check` passes.
6. `git diff --name-status` contains only the approved documentation/context
   migration paths; no application/PAPER path changed.

## Receipt

Update this file through the required lifecycle:

```text
READY → IN_PROGRESS → DONE | BLOCKED | DONE_WITH_CONCERNS
```

On completion, include the final state, changed paths, checks/evidence, and any
concerns. Do not edit another role's artifact.

## Completion receipt

- **State:** `DONE`
- **Files changed:** Rewrote `AGENTS.md` and `README.md`; added `DOMAIN.md`; deleted
  `CURRENT.md`, `memory.md`, every listed `context/` file/asset, and the six approved
  empty root dispatch placeholders. This task receipt is the only workstream artifact
  updated.
- **Checks / evidence:** `AGENTS.md` 81 lines and `DOMAIN.md` 51 lines; custom
  documentation/static checks passed; current/root authority docs have no deleted-path
  references; README commands were checked against `pyproject.toml`, `package.json`,
  `alembic.ini`, and the source tree; all planned deletions are absent; dependency scan
  found no production, build, import, test, or workflow references; `git diff --check`
  passed; application, test, schema, migration, frontend, configuration, secret, and
  preserved dispatch paths are unchanged.
- **Findings / concerns:** Historical dispatch records retain old context references
  intentionally. No real deletion dependency was found; PAPER/LIVE remains explicitly
  future-only and was not used as current-capability evidence.
