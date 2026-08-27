# Foundation Freeze 02 — Experiment Correctness and Result Immutability

## Status

`APPROVED — implementation authorized with frozen Sharpe, canonical equity, result-quality, and completion-invariant decisions`

Branch: `solo/foundation-freeze-02-experiment-correctness`
Base SHA: `eb64aa09dffdf001283cdf6bc5c9bb152d304b67`
Current phase: `MERGE APPROVAL GATE`
Next action: developer merge approval; then perform GIT END as the final workflow step.

## Authority and scope

The user-provided Foundation Freeze 02 contract is authoritative. The corrected
`ema_sweep_confirmation_break.v2` from Foundation Freeze 01 is authoritative.
This is Critical because it governs temporal integrity, execution, P&L/equity,
determinism, and immutable historical results.

In scope: audit and smallest remediation design for V2 sequencing, executable
behavior, accounting/equity, metrics, persisted results, read performance,
reproducibility, result quality, failure classification, and legacy authority.

Out of scope: Strategy rules, historical-data acquisition/loading, UI design,
PAPER/LIVE, broker abstractions, Risk architecture except proven Experiment
defects, and Foundation Freeze 03.

## Required first-pass deliverables

- Trace the complete V2 path and one Trade through final accounting.
- Trace completion/persistence and list/detail reads.
- Audit canonical equity ordering and every headline metric methodology.
- Audit fingerprints, ambiguity/result quality, and runner failure classification.
- Classify authoritative, reachable legacy, dead legacy, and stale specification.
- Propose the smallest authoritative remediation with exact files/seams.
- Define ordered implementation tasks and validation evidence.

## Task state

- `T001` ARCHITECT: done — authoritative audit and architecture remediation.
- `T002` BUILD: done — persisted result-state/schema and immutability.
- `T003` BUILD: done — V2 completion, metrics, quality, fingerprint.
- `T004` BUILD: done — persisted-result read paths and bounded evidence reads.
- `T005` BUILD: done — typed failure classification and regression coverage.
- `T006` BUILD: done — validation remediation (migration graph and accounting classification).
- `T007` BUILD: done — comparison read-path compatibility remediation.
- Prior BUILD remediation, validation, and review passed without a configured DB;
  live PostgreSQL validation now has blockers. Merge approval is blocked.
- `T008` BUILD: done — migration cycle and stale completed-fixture remediation.
- VALIDATION passed against PostgreSQL; REVIEW passed.
- VALIDATE/REVIEW: not started.

## Approval gate

Developer approval was received on 2026-08-27. GIT START completed from the
recorded base SHA; application and test implementation may proceed on this branch.
