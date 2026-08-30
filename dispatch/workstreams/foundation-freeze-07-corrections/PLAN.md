# Foundation Freeze 07 — Post-merge Corrections Plan

## Classification and approval

- Classification: `Critical` remediation
- Status: `READY_FOR_USER — merge approval required`
- Developer approval: explicit approval received for the two listed corrections.
- Architecture: use the already frozen Freeze 07 architecture; do not reopen or
  change its technical contracts.
- Scope: only DELETE lock ownership/order and exact 0021 downgrade restoration.
- Exclusions: no pre-PAPER audit, PAPER/LIVE work, Strategy authoring, unrelated
  code, or broad validation.

## Git start

- Branch: `solo/foundation-freeze-07-corrections`
- Base SHA: `82b009fd2e426f51dba1fa12e3d9c8e5ff0a8578`
- GIT START completed from local `main` at that SHA.
- Known pre-existing untracked paths `.codegraph/` and `frontend/.env.local`
  remain excluded.

## Frozen correction requirements

### C1 — DELETE lock order

The DELETE API must not lock Experiment before confirmation projection locks its
DatasetSnapshot. Use one consistent caller/service boundary with this order:

1. non-lock read of Experiment sufficient to identify the snapshot;
2. `DatasetSnapshot FOR UPDATE`;
3. `Experiment FOR UPDATE`;
4. confirmation facts, validation, and deletion in the same caller-owned
   transaction.

Eliminate duplicate lock ownership rather than adding a parallel preflight. Keep
exact confirmation facts, locked RUNNING precedence, stale-status mismatch
behavior, one transaction, and all existing deletion-service semantics.

### C2 — Exact 0021 downgrade restoration

Migration `0021` downgrade must restore the exact revision-0020
`snapshot_v2_append_only_guard()` function contract: row trigger handles UPDATE/
DELETE, while INSERT validation belongs to the `snapshot_v2_insert_guard`
statement trigger. Add migration-cycle proof comparing the restored function
definition and trigger contract, not merely existence or generic immutability.

## Acceptance

- C1 targeted API/service tests prove snapshot-before-Experiment locking and no
  second contradictory lock path; all existing confirmation/error semantics pass.
- C2 targeted migration tests prove exact 0020 function/trigger restoration and
  preserve upgrade/downgrade behavior.
- Targeted validation and targeted rereview both pass with no unresolved
  Critical/Important findings.

## Task state

| Task | Status | Dependency |
| ---- | ------ | ---------- |
| T001 — DELETE lock order | `DONE` | — |
| T002 — Exact downgrade restoration | `DONE` | — |

## Next action

Both BUILD tasks are `DONE`; targeted validation and rereview are `PASS` with no
unresolved Critical/Important findings. Await explicit merge approval; do not
begin pre-PAPER/PAPER work.
