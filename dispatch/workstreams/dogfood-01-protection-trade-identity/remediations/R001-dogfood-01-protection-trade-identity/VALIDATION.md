# R001 VALIDATION — Reject Explicit Null Trade Account Identity

- **Remediation ID:** `R001`
- **Workstream:** `dogfood-01-protection-trade-identity`
- **Role:** `VALIDATE`
- **Status:** `PASS`
- **Branch:** `solo/dogfood-01-protection-trade-identity`
- **CWD:** `/Users/vike/Desktop/atlas`

## Receipt

Independently validated R001 against immutable originating finding I-001 in `REVIEW.md`,
the `R001 BUILD.md` receipt, frozen `PLAN.md`/`ARCHITECTURE.md`, T001 evidence, and the
completed root validation/review artifacts. The execution uncertain-entry and protection
predicates, and the OANDA reconciliation attribution predicate, now distinguish an omitted
`accountID` key from a supplied value. Accountless and explicitly matching account Trade
objects remain accepted at their public seams; explicit `null` and mismatches fail closed.

The protection negative path remains incomplete with Stop unproven, leaves the Target
`NOT_ATTEMPTED`, and performs no Target PUT. Reconciliation remains read-only and reports
the contradictory Trade as unattributable. No raw provider mapping is fabricated or changed.

## Ordered checks and evidence

1. Targeted R001 explicit-null regressions first:
   `uv run pytest backend/tests/integrations/test_oanda_entry_mutation.py
   backend/tests/integrations/test_oanda_protection_completion.py
   backend/tests/integrations/test_oanda_reconciliation.py -k 'explicit_null' -q`
   — **3 passed, 44 deselected**.
2. Execution/protection and uncertain-entry public seams:
   — **33 passed**. Accountless and matching-account cases remain valid; wrong reader
   account, contradictory supplied account, and explicit null cannot produce an authorized
   protection path.
3. OANDA reconciliation attribution plus provider read-failure/coordinator behavior:
   — **43 passed**. Accountless and matching-account Trades are attributable; explicit null
   and mismatches are not attributable; read-failure and coordinator semantics remain green.
4. Durable execution/composition barriers: **18 passed**. Runtime completion,
   orchestration, cycle, and activation blocking coverage: **102 passed**.
5. Changed-slice gates: Ruff format **passed** (7 files), Ruff lint **passed**, Pyright
   **0 errors / 0 warnings / 0 informations**, and `git diff --check` **passed**.
6. Safe backend suite, `uv run pytest -m 'not integration and not external' -q` — **1121
   passed, 4 skipped, 115 deselected**. Four pre-existing warnings were emitted.

## Scope and safety confirmation

- The tracked implementation/test diff remains confined to the approved OANDA execution,
  protection, uncertain-entry, reconciliation, durable/composition fixture, and operational
  dispatch seams. No persistence/schema or migration, provider-neutral reconciliation
  coordinator, Strategy, Risk, runtime authority, mutation behavior/payload, retry behavior,
  or historical Dogfood evidence changed.
- Durable ENTRY/TAKE_PROFIT barriers, owner fences, Stop-before-Target ordering, one-shot
  mutation, fail-closed uncertainty, runtime blocking, and read-only reconciliation remain
  covered by the passing suites above.
- No credentialed OANDA mutation, PAPER runtime start, activation, retry, historical repair,
  or Git history operation occurred. Repository remains on the required branch with expected
  uncommitted workstream changes.

## Findings and concerns

- **APPROVED-SCOPE / REGRESSION / IMPORTANT I-001:** **Resolved.** No unresolved CRITICAL or
  IMPORTANT issue remains.
- **TOOLING / NEW SCOPE / MINOR:** The frozen `ARCHITECTURE.md` still says
  “Implementation authorization: None” while the approved PLAN and completed task state
  otherwise. This inherited evidence metadata was not changed by VALIDATE and does not block
  this remediation PASS.
- **TOOLING / NEW SCOPE / MINOR:** The safe suite retains four pre-existing dependency/mark
  warnings; changed-slice format, lint, and type gates are clean.
