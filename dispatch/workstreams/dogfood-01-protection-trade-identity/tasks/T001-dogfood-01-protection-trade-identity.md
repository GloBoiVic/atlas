# T001 — Dogfood 01 Protection Trade Identity

- **Workstream:** `dogfood-01-protection-trade-identity`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Branch:** `solo/dogfood-01-protection-trade-identity`
- **Owner artifact:** this file

## Objective

Implement only the frozen account-scoped OANDA Trade identity repairs:

1. Prove execution/protection Trade readback account scope through the configured,
   validated account-bound reader rather than requiring or fabricating raw Trade
   `accountID`.
2. Preserve the same account-bound authority and exact Trade/Fill lineage for uncertain-entry
   shared Trade readback.
3. Treat a missing raw Trade `accountID` as valid for an account-scoped OANDA reconciliation
   Trade read; an explicitly supplied mismatch remains unattributable/conflict.

## Required behavior

- Return raw provider Trade mappings unmodified; never add `accountID` to payloads or fixtures.
- Preserve strict Trade identity, Fill, Stop, Target, ordering, durable claim, owner-fence,
  one-shot mutation, fail-closed uncertainty, runtime-blocking, and read-only reconciliation
  semantics from `PLAN.md` and `ARCHITECTURE.md`.
- Do not modify provider-neutral reconciliation coordinator semantics.
- Do not change Strategy methodology, Risk policy, persistence/schema, runtime authority,
  mutation barriers, or retry semantics.
- Do not make credentialed OANDA mutations, start PAPER runtime, create an activation, or
  repair/alter historical Dogfood 01 state.

## Implementation seams and evidence

Use only the directly affected seams identified by the frozen architecture, including:

- `backend/integrations/oanda/execution.py`
- `backend/integrations/oanda/reconciliation.py`
- directly relevant OANDA execution/protection, uncertain-entry, composition, durable,
  runtime, and reconciliation tests/fixtures.

The regression suite must use real-shape accountless Trade fixtures and prove matching and
contradictory account cases, exact Trade/Stop identity, Stop-before-Target ordering, no Stop
repair, at-most-one existing Target PUT, durable barriers, incomplete/runtime blocking, and
unchanged reconciliation read-failure semantics.

## Checks

Run focused real-shape execution/protection tests first, then uncertain-entry/shared-readback,
OANDA reconciliation attribution/read-failure, durable barrier/persistence, and runtime
blocking coverage. Run appropriate safe backend tests plus format/lint/type checks for the
changed slice. Stop and report if persistence/schema or provider-neutral reconciliation
semantics would need to change.

## Worker Evidence

BUILD completed within the frozen execution and reconciliation seams.

- Execution readback protocols now expose the validated configured account; the
  Practice reader validates account-ID shape, preserves account-scoped GET paths,
  and returns provider Trade mappings without fabrication.
- Uncertain-entry and protection Trade matching now use configured reader account
  authority, accept documented accountless Trade payloads, and reject explicit
  contradictory account identity.
- Reconciliation Trade attribution accepts accountless account-scoped Trade
  payloads while retaining explicit mismatch conflict behavior. No coordinator,
  persistence, schema, runtime authority, or mutation barrier semantics changed.
- Real-shape fixtures and public-seam coverage were updated for protection,
  uncertain entry, composition, durable barriers, runtime blocking, and
  reconciliation.

Checks:

- Focused execution/protection, uncertain-entry/shared-readback, reconciliation,
  durable, and runtime suite: `147 passed`.
- Safe backend suite: `1115 passed, 4 skipped, 115 deselected`.
- Changed-slice Ruff format, Ruff lint, and Pyright: passed.
- `git diff --check`: passed.

No credentialed OANDA mutation, PAPER runtime start, activation, retry, or
historical Dogfood 01 state change was performed.

Concerns: repository-wide Ruff format/lint and Pyright remain non-clean due to
pre-existing unrelated findings outside this task; the changed slice is clean.
