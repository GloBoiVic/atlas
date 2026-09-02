# T003 — PAPER 05 Bounded Reconciliation

- **Status:** `DONE_WITH_CONCERNS`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Base:** `7a3204c41a394172752ab64b8aeab3f8fbcccf5e`
- **Owned artifact:** this file
- **Depends on:** T001 persistence foundation, R001/R002 remediation chain, and T002 durable execution integration; frozen `PLAN.md` and `ARCHITECTURE.md`

## Objective

Implement the bounded, read-only PAPER reconciliation coordinator that can
re-inspect one uncertain or protection-incomplete OANDA Practice attempt without
resubmitting, repairing, cancelling, closing, reducing, or otherwise mutating
broker exposure.

## In scope

- Add a provider-neutral reconciliation service/coordinator that loads one
  durable attempt, takes the required row lock/version guard, performs a finite
  provider GET sequence outside the final write transaction, and applies only
  validated observations/findings/projection updates.
- For `UNKNOWN`/claimed entry, use the original deterministic client order ID:
  exact Order read; terminal transaction read when attributable; Trade read when
  an attributable Fill is possible; and one coherent account-details safety read
  when no Fill is proven. Not-found must remain unresolved.
- For known Fill/protection-incomplete attempts, read the durable Trade ID once,
  validate account/instrument/Trade/client identity, independently classify the
  expected Stop Loss and Take Profit, and promote only exact coherent pending
  protection to `FILLED_PROTECTED`.
- Add bounded OANDA transaction-ID-range read support where the durable
  transaction frontier requires it. Use numeric OANDA transaction IDs, explicit
  finite limits, and no unbounded polling or global cursor. Retain every read's
  request/transaction/batch/related/frontier/timestamp provenance that the
  provider supplies; never invent request IDs or atomicity.
- Normalize provider facts at the OANDA boundary into the existing strict
  provider-neutral observation contract. Persist observations/findings before
  projection changes and advance an attempt frontier only in the same local
  transaction after validation.
- Persist append-only reconciliation runs/findings with `PROVEN`, `UNRESOLVED`,
  `CONFLICT`, or `FAILED` status, explicit non-atomic read sets, bounded
  diagnostics, and no raw provider payloads/secrets.
- Fail closed for stale/partial/malformed reads, contradictory Atlas/broker
  state, wrong account/instrument/units/client IDs, un-attributable provider
  objects, unexpected account exposure/pending Orders, and lost ownership.
- Add deterministic MockTransport/fake tests for every bounded sequence,
  transaction-range boundaries, not-found, terminal reject/cancel/fill,
  protection states, stale frontiers, conflicts, read failures, concurrent
  reconciliation, idempotent observations, and zero POST/PUT calls.

## Explicit non-goals

- No runtime loop, scheduler, worker, activation, API/UI, resumption policy, or
  automatic invocation cadence.
- No POST/PUT/cancel/close/reduce/protection repair, retry, LIVE, credentials,
  multi-account/instrument, partial/multi-fill, closed-Trade accounting, PnL,
  global synchronization, or general multi-broker abstraction.
- No historical Experiment persistence or Strategy/Risk/PAPER 04 semantic
  changes. Do not turn separate provider GETs into an atomic snapshot.

## Completion requirements

1. Reconciliation is strictly read-only at the provider boundary and contains
   no mutation-capable collaborator.
2. Every bounded path preserves durable Fill truth, independently tracks Stop
   and Take Profit, and never turns absence or uncertainty into flat/rejected/
   cancelled success.
3. Exact attributable provider facts precede any projection/frontier update;
   contradictory or stale evidence remains blocked and append-only.
4. Transaction ranges are numeric, bounded, provenance-retaining, and do not
   create an unbounded polling or global cursor behavior.
5. Repeated/restarted/concurrent reconciliation is safe and never creates a
   mutation claim or broker POST/PUT.
6. Deterministic focused tests and relevant static checks pass; update this
   receipt before advancing to independent validation.

## Worker Evidence

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T003-paper-05-reconciliation.md`
FILES CHANGED:

- `backend/paper/reconciliation.py`
- `backend/paper/persistence_contracts.py`
- `backend/paper/__init__.py`
- `backend/persistence/paper_execution_repository.py`
- `backend/integrations/oanda/reconciliation.py`
- `backend/integrations/oanda/request.py`
- `backend/integrations/oanda/execution_account.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/paper/test_reconciliation.py`
- `backend/tests/integrations/test_oanda_reconciliation.py`

CHECKS / EVIDENCE:

- `uv run pytest -q backend/tests/paper/test_reconciliation.py backend/tests/integrations/test_oanda_reconciliation.py backend/tests/paper/test_durable_execution.py backend/tests/paper/test_persistence_contracts.py backend/tests/integrations/test_oanda_entry_mutation.py backend/tests/integrations/test_oanda_request.py` — 87 passed.
- `uv run pytest -q -m "not integration and not external"` — 944 passed, 4 skipped.
- Targeted Ruff check/format and Pyright for the reconciliation implementation/tests — passed with no errors.
- MockTransport coverage verifies bounded numeric range reads, request provenance, not-found, fill/protection normalization, and zero non-GET requests.

FINDINGS / CONCERNS:

- The OANDA reconciliation exports were made lazy to break an import cycle discovered during focused test collection.
- Integration/PostgreSQL validation was not run because `ATLAS_TEST_DATABASE_URL` was not provided; use a dedicated `*_test` database for the integration gate.
- Whole-repository `ruff check backend`, `ruff format --check backend`, and `pyright backend` still report pre-existing unrelated failures; the changed reconciliation slice passes targeted checks.

<!--
Original completion template:

```text
ROLE: BUILD
STATUS: DONE | BLOCKED | DONE_WITH_CONCERNS
ARTIFACT: this file
FILES CHANGED: <paths>
CHECKS / EVIDENCE: <brief result>
FINDINGS / CONCERNS: <brief result>
```
-->
