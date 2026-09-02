# R002 — PAPER 05 Observation Attribution Remediation

- **Remediation ID:** `R002`
- **Status:** `DONE`
- **Role:** `BUILD`
- **Workstream:** `paper-05-persistence-reconciliation`
- **Branch:** `solo/paper-05-persistence-reconciliation`
- **Origin finding:** `dispatch/workstreams/paper-05-persistence-reconciliation/tasks/T002-paper-05-durable-execution-REVIEW.md`, finding 1
- **Finding severity:** `IMPORTANT` / `PRODUCT`
- **Related original task:** `T002-paper-05-durable-execution`
- **Approved requirement/invariant violated:** provider facts must remain distinct from Atlas conclusions; a no-PUT protection read must be correctly typed as `TRADE_DETAIL` and must not be persisted as a Take Profit mutation response or attributed to the ENTRY claim

## Exact remediation outcome

Correct the durable protection path so that:

1. When OANDA protection completion reads the Trade/Stop state and returns
   `FILLED_PROTECTION_INCOMPLETE` before the dependent Take Profit PUT, the
   durable coordinator persists the normalized pre-PUT Trade-detail observation
   with the correct read/object kind and without a mutation-attempt claim.
2. A `TAKE_PROFIT_MUTATION_RESPONSE` observation is persisted only when the
   permanent `TAKE_PROFIT` claim was committed and the dependent PUT boundary
   was actually reached. It must never be synthesized from an incomplete
   protection result or linked to the ENTRY claim.
3. The normalized observation remains provider-fact evidence distinct from the
   outcome projection; no-PUT paths remain incomplete/blocked and exact valid
   protection remains unchanged.
4. Add a deterministic regression probe for missing/unprovable Trade or Stop
   protection proving the observation kind/claim attribution and proving no PUT
   occurred, plus preserve existing successful and uncertain PUT tests.

## Affected implementation seams

- `backend/paper/durable_execution.py`
- `backend/paper/execution_application.py` and/or
  `backend/integrations/oanda/execution.py` only for the narrow observation
  callback/result plumbing required to expose the already performed Trade read
- `backend/tests/paper/test_durable_execution.py` and focused OANDA tests

## Explicit out-of-scope items

- No reconciliation coordinator, transaction-ID polling, schema redesign,
  runtime, activation, scheduler, retry, repair, cancel/close/reduce, LIVE,
  credential, or real broker changes.
- Do not invent provider facts or classify not-found as rejection/cancellation.
- Do not alter PAPER 04 protection semantics, Strategy/Risk behavior, repository
  immutability, or the existing outcome state machine.

## Regression evidence required

- Deterministic no-PUT protection-read test asserts `TRADE_DETAIL`, nullable
  mutation claim, and zero PUT calls.
- Existing focused durable/PAPER/OANDA tests remain green, including exact
  protected path and uncertain Take Profit path.
- Relevant static checks and `git diff --check` pass.
- No real provider call or credential use.

## Worker Evidence

Populate this artifact on completion with the remediation BUILD receipt. Do not
edit the failed review or any completed validation/evidence artifact.

## Completion Receipt

ROLE: BUILD
STATUS: DONE
ARTIFACT: `dispatch/workstreams/paper-05-persistence-reconciliation/remediations/R002-paper-05-observation-attribution/BUILD.md`
FILES CHANGED: `backend/paper/durable_execution.py`, `backend/paper/execution_application.py`, `backend/integrations/oanda/execution.py`, `backend/tests/paper/test_durable_execution.py`
CHECKS / EVIDENCE:

- Focused durable/PAPER/OANDA suite: `68 passed`.
- Broad safe backend suite: `933 passed, 4 skipped, 97 deselected`; four existing warnings.
- Changed-slice Ruff format/check: passed.
- Changed-slice Pyright: `0 errors`.
- `git diff --check`: passed.
- Deterministic public-seam regression covers missing Trade and Stop-mismatch no-PUT paths: `TRADE_DETAIL`/`TRADE`, nullable mutation claim, and zero PUT calls. Protected and uncertain PUT coverage remains green.

FINDINGS / CONCERNS: Added the narrow `after_trade_detail` callback for pre-PUT incomplete protection reads. Durable persistence now records those facts without a claim, applies the incomplete result without synthesizing an observation, and emits TAKE_PROFIT mutation observations only through the post-PUT callback with the committed TAKE_PROFIT claim. No provider mutation, reconciliation, retry, repair, runtime, activation, credential, or schema scope was added.
