# REVIEW — Dogfood 01 Protection Trade Identity

- **Role:** `REVIEW`
- **Workstream:** `dogfood-01-protection-trade-identity`
- **Branch:** `solo/dogfood-01-protection-trade-identity`
- **CWD:** `/Users/vike/Desktop/atlas`
- **Task:** `T001`
- **Owned artifact:** `dispatch/workstreams/dogfood-01-protection-trade-identity/REVIEW.md`
- **Specialist skills:** `tdd`
- **Status:** `FAIL`

## Independent verdict

**FAIL.** One unresolved IMPORTANT approved-scope regression remains. The normal
account-scoped path is bounded and capital-safe, but explicit `null` top-level Trade
account identity is accepted as if the field were absent. This violates the frozen
strict identity/fail-closed contract and must be corrected before merge approval.

## Review scope and evidence

- Verified repository root/CWD `/Users/vike/Desktop/atlas`, required branch, and
  `HEAD`/`main` at the approved base `ebb2ed98d52aa28f30870f94fdc77f516cea7742`.
- Reviewed the frozen `PLAN.md`, `ARCHITECTURE.md`, completed BUILD receipt
  `tasks/T001-dogfood-01-protection-trade-identity.md`, PASS `VALIDATION.md`, and
  the complete tracked and workstream evidence diff.
- The implementation diff is confined to the approved OANDA execution readback,
  protection, uncertain-entry, reconciliation attribution, directly affected
  deterministic tests, and expected `dispatch/ACTIVE.md` state. No persistence or
  schema, provider-neutral coordinator, Strategy, Risk, runtime-authority, or
  historical Dogfood evidence changes are present.
- The reader exposes the validated configured account, uses account-scoped GETs, and
  returns the provider Trade mapping without fabrication. Accountless real-shape
  fixtures are used; contradictory account fixtures are intentional negatives.
- Exact Trade/Fill/Stop predicates, Stop-before-Target ordering, durable claim and
  owner barriers, one-shot/no-retry mutation behavior, runtime blocking, and
  read-only reconciliation behavior are otherwise unchanged by the diff.

## Findings

| Severity | Classification | Type | Finding |
| --- | --- | --- | --- |
| CRITICAL | PRODUCT | DEFECT | None observed. |
| IMPORTANT | REGRESSION | DEFECT | **I-001 — explicit null Trade account identity is accepted.** |
| MINOR | TOOLING | NEW SCOPE | `ARCHITECTURE.md` still says implementation authorization is `None`, contradicting the approved PLAN/T001 state; this is evidence metadata and was not changed. |
| MINOR | TOOLING | NEW SCOPE | VALIDATION records a wrapper-timeout retry and pre-existing warnings/repository-wide static findings; changed-slice gates are clean. |

### I-001 — explicit null Trade account identity is accepted

**Locations:** `backend/integrations/oanda/execution.py:1174` and `:1793`, and
`backend/integrations/oanda/reconciliation.py:587`.

Each new predicate uses `trade.get("accountID") in (None, account_id)`. That
correctly permits an omitted field, but also permits a mapping that explicitly
contains `{"accountID": None}`. The frozen contract permits omission only; when
the field is supplied, its value must equal the already-proven configured/context
account. An explicit null is malformed/nonmatching identity and must fail closed.

This is a regression from the former exact equality check. In execution it can
allow an uncertain-entry Trade to become a Fill and can allow protection to pass
Stop confirmation and issue the existing Target PUT. In reconciliation it can mark
the Trade attributable. Add public-seam negative coverage and distinguish key
absence from an explicit null (for example, with a missing-key sentinel) in all
three predicates. Do not broaden authority or add recovery/mutation behavior.

## Checks and capital-safety boundary

- Independent focused execution/protection/uncertain-entry/reconciliation/durable
  run: **88 passed**.
- Independent runtime completion/orchestration/cycle/activation run: **102 passed**.
- Changed-file Ruff format/lint and Pyright: **passed; 0 errors, 0 warnings**.
- `git diff --check`: **passed**. The supplied VALIDATION receipt also records the
  safe backend suite at **1115 passed, 4 skipped, 115 deselected**.
- No credentialed OANDA request, broker mutation, PAPER runtime start, activation,
  retry, historical repair, or Git history operation occurred.
- Git remains uncommitted with the expected application/test/dispatch changes and
  untracked workstream evidence; no non-owned artifact was modified by REVIEW.

## Merge recommendation

Do not merge or authorize runtime/broker activity until I-001 is remediated and
independently validated. This review does not modify application code, tests, or
Git history.
