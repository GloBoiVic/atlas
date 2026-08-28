# T001 — Context Authority Documentation Cleanup

Status: `DONE`

## Assignment

Implement the approved Context Authority Cleanup — Pass 1 in the repository root and on the active branch.

Update only the developer-listed files, delete `context/.DS_Store`, and preserve `context/product/north-star.md`. Do not modify application code, tests, migrations, or dispatch history. Make surgical edits that promote Freeze 01–03 contracts into permanent architecture/context authority, correct native M15 plus sparse M1 semantics, update current Strategy terminology/behavior, correct status and README usage, and add the authority map. Do not begin Pass 2 or commit.

## Required checks

- Inspect the full diff and verify only approved documentation paths plus the required workstream receipt changed.
- Search for stale `EMA Sweep Engulfing`, M1→derived-M15 claims, and incomplete Freeze 03/Phase 6 claims.
- Record remaining occurrences and whether each is intentionally historical.
- Run `git diff --check`.

## Completion receipt

### Result

Updated current/root documentation and promoted Freeze 01–03 authority into permanent context. Current Strategy is named as EMA Sweep Confirmation Break v2; the authoritative historical path is documented as native M15 MID analysis with sparse M1 BID/ASK execution. Added the authority map, corrected current status and README usage, and deleted `context/.DS_Store`. `context/product/north-star.md` was preserved.

### Changed paths

`AGENTS.md`, `CURRENT.md`, `README.md`, `context/index.md`, approved files under
`context/architecture/`, `context/development/agent-workflow.md`,
`context/features/experiments.md`, `historical-data.md`, `reference-strategy.md`,
`context/product/vision.md`, and `context/roadmap/roadmap.md`; deletion of
`context/.DS_Store`. The nine previously out-of-scope design/feature files were
restored exactly to HEAD.

### Checks / evidence

- `git diff --check`: PASS.
- Scope check: PASS. All nine out-of-scope files report `HEAD_MATCH`; tracked edits are limited to the approved root/context files plus the owned receipt. Pre-existing `dispatch/ACTIVE.md` remains untouched by this remediation.
- Required searches run for `EMA Sweep Engulfing`, M1→derived-M15 claims, and incomplete Freeze 03/Phase 6 claims.
- Remaining legacy matches are intentionally historical/compatibility examples in restored out-of-scope docs, explicit contradiction warnings in current authority, or roadmap history; no active M1→derived-M15 authority claim remains.
- No application code, tests, migrations, or `context/product/north-star.md` changes. No commit created.

### Findings / concerns

Remediation complete: the nine out-of-scope design/feature files were restored
exactly to HEAD, and the four omitted approved authority files were updated.
