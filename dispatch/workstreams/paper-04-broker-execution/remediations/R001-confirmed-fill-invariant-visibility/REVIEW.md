# R001 REVIEW — Confirmed Fill invariant visibility

- **Status:** PASS
- **Role:** REVIEW
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Origin:** `CRITICAL C-001` in the original immutable REVIEW.md
- **Scope:** Targeted independent rereview of R001 BUILD evidence, R001 VALIDATION.md, remediation diff, and the frozen confirmed-Fill outcome contract.
- **Receipt:** Complete and immutable independent remediation review receipt.

## Decision

PASS. R001 remediates C-001 within the frozen five-outcome contract. A broker-confirmed
full Fill that violates the bound, Stop geometry, or approved actual-risk budget remains
visible as `FILLED_PROTECTION_INCOMPLETE`, with bounded Fill facts and transaction
provenance retained. The application returns before protection completion, so no target
mutation, repair, retry, or second entry submission follows these invariant failures.

## Reviewed evidence

Reviewed the original immutable `REVIEW.md` C-001 finding, R001 `BUILD.md`, R001
`VALIDATION.md`, frozen `PLAN.md` and `ARCHITECTURE.md`, the remediation implementation
and focused composition/test diff, and the declared-branch working tree. Earlier review,
validation, and planning evidence remain immutable.

Independent checks:

- `uv run pytest backend/tests/paper/test_execution_composition.py backend/tests/integrations/test_oanda_entry_mutation.py backend/tests/integrations/test_oanda_execution_translation.py backend/tests/integrations/test_oanda_protection_completion.py -q`: **37 passed**.
- `uv run pytest -m "not integration and not external" -q`: **922 passed, 4 skipped, 88 deselected**; only the existing four warnings.
- Changed remediation files: `ruff format --check`: **passed**; `ruff check`: **passed**; `pyright`: **0 errors, 0 warnings, 0 informations**.
- `git diff --check`: **passed**.
- Tests use injected fakes and `httpx.MockTransport`; no real OANDA request, credentialed mutation, or capital exposure occurred.

## Judgment

| Review point | Judgment | Evidence |
|---|---|---|
| Validated Fill facts survive worse-than-bound Fill | PASS | `_filled_result` constructs `BrokerFillFacts` from the validated order/fill/trade facts before raising `ENTRY_FILL_BOUND_VIOLATION`; the application carries those facts into the result. Composition coverage uses Fill `1.10021` and retains Order `1001`, Fill transaction `1002`, Trade `7001`, actual price/risk, and provenance. |
| Validated Fill facts survive wrong-side Stop geometry | PASS | The geometry check occurs after the validated Fill is constructed and raises `ENTRY_FILL_STOP_GEOMETRY_VIOLATION` with the same carried facts/provenance. Composition coverage uses Fill `1.09490` and asserts the retained actual price/risk and identifiers. |
| Validated Fill facts survive actual-risk-budget violation | PASS | Actual initial risk is derived from the broker-authoritative `tradeOpened.price` and validated full quantity before the budget check. The composition test compares `98.07300` against a patched budget of `90` and retains the Fill/provenance facts with `ENTRY_FILL_RISK_BUDGET_EXCEEDED`. |
| Outcome is not `UNKNOWN` | PASS | `PaperExecutionApplication` catches the carried invariant error and returns `FILLED_PROTECTION_INCOMPLETE`; its fallback to `_unknown_result` applies only when the required carried facts are absent. |
| Protection/target mutation is prevented | PASS | The invariant-error branch returns immediately with both protection legs `NOT_ATTEMPTED`; composition tests assert zero protection calls for all three violations. |
| Retry, repair, and resubmission are prevented | PASS | The entry adapter marks the attempt before POST and has no recovery POST; the one-shot requester does not retry. The application never invokes protection completion for these branches, and the focused tests assert one entry call and zero dependent mutation calls. |
| Scope and regression boundary | PASS | The remediation is limited to entry normalization, application entry-result handling, and focused deterministic tests. No frozen outcome, Risk/Strategy meaning, persistence, runtime, API/UI, historical execution, activation, or LIVE behavior was changed. No new Critical or Important finding is introduced. |

## Findings

None. Original C-001 is remediated and independently verified. No separate Critical or
Important finding was identified in the bounded R001 change.

## Residual boundary

The inherited PAPER 04 snapshot-to-mutation race and durable reconciliation boundary
remain explicitly outside R001/PAPER 04, as required by the frozen architecture. This
does not block the remediation PASS and does not authorize real OANDA mutation or PAPER
activation.
