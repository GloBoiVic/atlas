# R003 Validation — PAPER 05 Attribution, Frontier + Provenance

- **Remediation ID:** `R003`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Role:** `VALIDATE`
- **Status:** `FAIL`
- **Origin:** T003 bounded reconciliation validation failure, findings 1–9; developer-authorized single post-cap PRODUCT-BLOCKER path

## Validation mandate

Independently validate R003 against the frozen `PLAN.md` and
`ARCHITECTURE.md`, the root workstream validation, all prior task and remediation
receipts, R003 BUILD receipt, current implementation/test diff, and every
deterministic T003 failing probe. First rerun all probes that caused the current
block. Then verify the full R003 acceptance matrix, focused PostgreSQL repository
and migration evidence, focused PAPER/persistence/reconciliation tests, broad safe
backend tests, changed-slice Ruff/Pyright, Alembic checks, and `git diff --check`.

Use deterministic fakes/`httpx.MockTransport` only. No real OANDA mutation,
credential, activation, runtime, or capital-capable action is permitted. This
role writes only this artifact and must not modify application, tests, fixtures,
migrations, or any prior evidence artifact.

## Independent judgment

R003 does not pass the frozen PAPER 05 reconciliation contract. The remediation
resolves the T003 probes for strict provider attribution, bounded reject/cancel
recovery, known-Fill Trade verification, range provenance, numeric frontiers,
and 404 RequestID retention. However, a later attributable Fill is not marked
as a reconciliation conflict when the durable attempt already has a terminal
`REJECTED` or `CANCELLED` outcome. This leaves one approved Fill-versus-terminal
contradiction path unresolved and blocks this Critical remediation.

## Acceptance evidence

- The focused R003/PAPER/OANDA suite passed: **102 passed**. This includes the
  changed-quantity identity probe, strict Stop/Take Profit attribution, bounded
  `MARKET_ORDER_REJECT` and create/cancel recovery, provider request/identity
  mismatches, known-Fill Trade mismatches, unattributed closed Trade, range
  contradiction, numeric frontier, range provenance, and supplied/absent 404
  RequestID regressions.
- The dedicated PostgreSQL repository suite passed: **9 passed** in the
  `paper05_validation` schema. Existing row-lock, immutable evidence, Fill
  non-erasure, claim uniqueness, stale projection, and append-only guard
  evidence remains green.
- The provider boundary remains GET-only in the reconciliation adapter; the
  deterministic MockTransport coverage observed no POST/PUT calls.
- The broad safe backend suite passed: **963 passed, 4 skipped, 97
  deselected**, with four existing warnings.
- Changed-slice Ruff format/check passed, changed-slice Pyright reported **0
  errors**, and `git diff --check` passed.
- With the dedicated test URL and `PGOPTIONS='-c
  search_path=paper05_validation'`, `alembic current` reported
  `0022_paper_persistence (head)` and `alembic check` reported no new upgrade
  operations. Migration revision tests passed (**2 passed**); the migration
  integration cycle had **1 passed, 2 setup failures** because its fixture
  hard-codes `DROP SCHEMA public CASCADE` and the configured role does not own
  `public`.
- A deterministic coordinator probe using only the existing in-process fakes
  reproduced the remaining contradiction: prior `REJECTED` and prior
  `CANCELLED` attempts, followed by an exact attributable Fill and a missing
  Trade read, both returned `UNRESOLVED` with
  `FILLED_PROTECTION_INCOMPLETE` and findings lacking `CONFLICT`.
- No real OANDA request, credential, activation, runtime, broker mutation, or
  capital-capable action was used. This role changed only this artifact.

## Findings

### IMPORTANT — PRODUCT — later attributable Fill after reject/cancel is not marked as conflict

The frozen architecture requires an extraordinary later attributable Fill after
an earlier `REJECTED` or `CANCELLED` projection to preserve the old terminal
observation, persist the Fill, advance execution truth to a filled outcome, and
set reconciliation status to `CONFLICT` (ARCHITECTURE §5.1 and §10; R003
requirement 8).

`PaperReconciliationCoordinator._consume_entry_terminal()` receives the current
outcome but does not compare it when accepting `read.fill`; it returns
`FILLED_PROTECTION_INCOMPLETE` without setting the coordinator's
`conflict_detected` flag. The exact-order/fill path therefore reaches the final
Trade read as though it were an ordinary Fill. In the independent deterministic
probe, the resulting status was `UNRESOLVED` (and with a matching protected
Trade it becomes `CONSISTENT`) rather than `CONFLICT` for both prior terminal
outcomes. The resulting reconciliation run can consequently overwrite the
execution projection without recording the required contradiction status.

The affected logic is in `backend/paper/reconciliation.py`, in the exact
terminal handling around `_consume_entry_terminal()` and its caller in
`reconcile()`. The range Fill-plus-reject/cancel regression passes, but it does
not cover a later exact Order/Transaction Fill after a previously persisted
reject/cancel outcome.

This is an IMPORTANT PRODUCT finding in the approved Critical scope. Validation
therefore remains **FAIL**; REVIEW must not proceed as a pass and no further
remediation chain is authorized by this receipt.

## Worker Evidence Receipt

ROLE: VALIDATE
STATUS: FAIL
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R003-paper-05-attribution-frontier-provenance/VALIDATION.md`
FILES CHANGED: this artifact only
CHECKS / EVIDENCE: Focused R003/PAPER/OANDA 102 passed; broad safe backend 963 passed, 4 skipped, 97 deselected; dedicated PostgreSQL repository 9 passed; migration revision 2 passed; dedicated Alembic head/check passed; migration fixture 1 passed and 2 setup-failed on the documented public-schema ownership limitation; scoped Ruff/Pyright and `git diff --check` passed; deterministic exact contradictory Fill probe reproduced the remaining finding.
FINDINGS / CONCERNS: FAIL — one IMPORTANT PRODUCT contradiction-handling gap remains. No real OANDA call, credential, activation, runtime, or capital-capable action occurred.
