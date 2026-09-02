# REVIEW — PAPER 04 Broker Execution

- **Status:** FAIL
- **Role:** REVIEW
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Base:** `53c6b229d6d5081e7853163d7e70952d14c33d61`
- **Receipt:** Complete and immutable independent Critical review receipt.

## Decision

FAIL. One unresolved CRITICAL capital-boundary finding remains. Do not merge,
activate PAPER, or permit broker mutation from this branch until it is remediated
and independently revalidated.

## Review scope and evidence

Reviewed the frozen `PLAN.md` and `ARCHITECTURE.md`, BUILD receipts T001–T005,
PASS `VALIDATION.md`, and the complete working-tree diff on the declared branch.
The diff is limited to the OANDA execution/capability adapters, PAPER execution
contracts/composition, focused deterministic tests, and SoloFlow receipts. No
historical execution, persistence, migration, runtime, API/UI, Strategy, Risk,
activation, or LIVE files were changed.

Independent checks:

- Focused new execution/capability suite: **59 passed**.
- Broad non-integration/non-external backend suite: **919 passed, 4 skipped,
  88 deselected**; only the documented pre-existing warnings.
- Changed-file `ruff format --check`: **passed**.
- Changed-file `ruff check`: **passed**.
- Changed-file `pyright`: **0 errors, 0 warnings**.
- `git diff --check`: **passed**.
- Full repository `pyright backend` still reports the pre-existing unrelated
  baseline errors outside this diff; this is not counted as a workstream finding.
- No real OANDA request, credentialed mutation, or capital exposure was used.

## Approved review checks

| Check | Judgment | Evidence |
|---|---|---|
| Pre-mutation non-MT4, GSLO, precision, and coherent-flat state gates | PASS | The application reads AccountProperties, one full Account Details snapshot, and EUR/USD capability before entry serialization/POST. GSLO mode, identity/frontier/count coherence, flat exposure, pending Orders, exact display precision, unit precision, and quantity bounds fail closed. |
| Exactly-once fresh Risk and stale approval isolation | PASS | `execute_paper_execution` accepts Strategy/Risk configuration rather than a `PaperRiskEvaluation`, reads current facts serially, and invokes `evaluate_paper_risk` once for a permitted invocation. A stale evaluation is rejected before reads/mutation. |
| Exact MARKET/FOK/OPEN_ONLY entry, bound, signed units, attached Stop, and no entry target | PASS for the normal path | Translation emits exact Risk `priceBound`, provider-side LONG/SHORT signed units, ordinary GTC `stopLossOnFill`, deterministic client IDs, and no `takeProfitOnFill`. No widening or rounding is present. |
| One-shot POST and bounded no-resubmit uncertainty | PASS | The mutation requester performs one non-retrying POST/PUT. The entry adapter marks an attempt before POST, uses bounded original-correlation GET readback, and never resubmits after transport, malformed-response, or readback uncertainty. |
| Actual `tradeOpened` Fill, full quantity, bound, and risk | **FAIL — CRITICAL C-001** | Valid full-Fill facts use `tradeOpened.price`, signed full quantity, bound, stop geometry, and actual-risk checks. However, a broker-confirmed full `tradeOpened` Fill that violates bound, stop geometry, or risk budget raises from `_filled_result`; the application catches it and constructs `UNKNOWN` with `fill=None` and empty transaction provenance. This erases known exposure and fails the required distinction between definite Fill and entry uncertainty. |
| Stop-before-target, actual-Fill target/no rounding, one-shot target PUT, and final protected versus incomplete outcomes | PASS for a valid Fill | Trade/Stop confirmation precedes target resolution; target uses actual Fill and exact provider precision; PUT contains only one exact GTC `takeProfit`; final Trade readback must prove both pending protections. Target failure/uncertainty remains `FILLED_PROTECTION_INCOMPLETE`, and no repair/retry occurs. |
| Historical isolation and no persistence/runtime/activation/LIVE widening | PASS | The actual diff contains no historical execution, persistence, migration, runtime, API/UI, activation, or LIVE changes. Deterministic tests use MockTransport/fakes only. |

## Findings

### CRITICAL C-001 — confirmed Fill invariant violations are downgraded to UNKNOWN

**Locations:** `backend/integrations/oanda/execution.py:740-763`
`_filled_result`; `backend/paper/execution_application.py:283-285` entry-mutation
exception handling and `:502-520` `_unknown_result`.

After validating `orderFillTransaction.tradeOpened`, full signed quantity, and
the actual Fill price, `_filled_result` raises for a worse-than-bound Fill,
wrong-side Stop geometry, or actual initial risk above the approved budget.
The application catches that exception and returns `UNKNOWN` without the broker
Order ID, Fill transaction ID, Trade ID, actual price, or actual risk. The frozen
architecture defines `UNKNOWN` as inability to establish entry exposure, while
these branches already establish a broker-confirmed exposure. This violates the
approved worse-than-bound invariant handling and the explicit requirement that a
definite Fill remain distinct from entry uncertainty; it also deprives
reconciliation of the identifiers needed to investigate the known exposure.

Remediation must preserve bounded broker Fill facts and transaction provenance
for these confirmed-exposure invariant failures and return a non-`UNKNOWN`
outcome consistent with the frozen five-outcome contract (or reconcile an
explicitly approved invariant outcome). Add composition-level deterministic
coverage for bound, stop-geometry, and risk-budget violations. No automatic
retry, repair, or resubmission should be introduced.

## Other concerns

- The documented snapshot-to-mutation race, durable attempt ownership, and
  UNKNOWN/protection reconciliation remain PAPER 05 boundaries; they are not
  silently treated as solved.
- No unresolved IMPORTANT finding was identified separately from C-001.

## Capital-boundary conclusion

No real OANDA mutation occurred during BUILD, VALIDATE, or REVIEW. The normal
supported path is narrowly scoped and fail-closed, but C-001 means this Critical
boundary is not yet a truthful result contract for every broker-confirmed Fill
case. Review remains FAIL until remediation and a new PASS validation receipt.
