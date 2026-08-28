# T004 — Final Surgical Corrections

Status: `DONE`

## Assignment

Apply exactly four documentation corrections, without broadening scope:

1. Correct README historical setup instructions to document the current V2 API/UI load-request workflow; label retained `atlas-data` commands explicitly legacy/non-authoritative.
2. Complete the authority hierarchy: link `context/product/north-star.md` from `vision.md`, reconcile `AGENTS.md` precedence by document ownership, and state that feature specs cannot override architecture.
3. Add concise Foundation Freezes 01–03 completion status and the planned-but-not-authorized Freeze 04 Experiment Engine Simplification direction to `CURRENT.md`.
4. Correct the reference Strategy Required Tests wording so W1–W5 is only the post-confirmation ARMED trigger-watch window and no fill expires at W6.

Inspect current source and preserve all existing good prose. Do not edit any file outside `README.md`, `AGENTS.md`, `context/product/vision.md`, `CURRENT.md`, and `context/features/reference-strategy.md`, apart from this receipt. Do not edit North Star, application code, tests, migrations, or dispatch history. Do not commit.

## Required checks

- Run the requested terminology/contradiction searches.
- Run `git diff --check`.
- Verify no out-of-scope files changed.

## Completion receipt

Implemented the four requested surgical documentation corrections. Changed
paths: `README.md`, `AGENTS.md`, `context/product/vision.md`, `CURRENT.md`,
`context/features/reference-strategy.md`, and this receipt. README now documents
the current V2 capability/load-request/status/resume/snapshot/Experiment flow
and labels `atlas-data` as legacy/non-authoritative. Authority ownership,
North Star linking, Freeze 01–03 completion, planned-but-not-authorized Freeze
04, and post-confirmation ARMED W1–W5/W6 test wording are corrected.

Checks: required searches run for stale `EMA Sweep Engulfing`, M1-derived-M15,
Freeze/status, V2 load-request, and W1–W6 terminology. Remaining stale-name and
M1-derived-M15 matches are historical/legacy text outside this task's approved
files; no active authority claim was introduced. `git diff --check` passed.
Working-tree review confirms task edits are limited to the approved files plus
this receipt; pre-existing changes and untracked files were preserved. No code,
tests, migrations, North Star content, or dispatch history were edited.
