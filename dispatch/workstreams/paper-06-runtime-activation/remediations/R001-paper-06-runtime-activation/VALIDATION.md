# R001 — Owner-loss fence before dependent protection mutation

- **Status:** `PASS`
- **Role:** `VALIDATE`
- **Workstream:** `paper-06-runtime-activation`
- **Branch:** `solo/paper-06-runtime-activation`
- **Origin:** `VALIDATION.md` `CRITICAL-01`

## Decision

`PASS` for the bounded R001 remediation. The committed Take Profit claim is
followed by an owner/generation fence immediately before the dependent
protection seam returns to the OANDA PUT. Owner loss retains the claim and
prevents the PUT; a valid same-process chain remains permitted.

## Evidence

- Reviewed the original `VALIDATION.md` `CRITICAL-01`, R001 `BUILD.md`,
  T006/T008 receipts, and the frozen ownership/protection requirements in
  `ARCHITECTURE.md` §§4, 7.7, 9.1, and 12.1.
- Inspected the remediation diff and current call path. `orchestration.py`
  supplies the owner/generation guard and cycle callback to
  `submit_claimed_entry`. In `durable_execution.py`, the sequence is:
  guard → TP claim commit → cycle callback → guard → return to the protection
  seam, whose next operation is the dependent PUT.
- The deterministic `httpx.MockTransport` regression
  `test_owner_loss_after_committed_take_profit_claim_never_puts` passed: the
  TP claim occurs once, the third owner fence fails, the result remains
  `FILLED_PROTECTION_INCOMPLETE`, and only the entry POST is observed.
- The valid same-process protection regression
  `test_stop_during_entry_network_preserves_one_authorized_protection_chain`
  passed with exactly `POST`, then `PUT` and `FILLED_PROTECTED`.

## Checks

| Check | Result |
| --- | --- |
| Focused R001/P05/runtime tests | `52 passed` |
| All deterministic runtime tests | `53 passed` |
| Relevant P05 protection/durable execution tests | `17 passed` |
| Changed-slice Ruff format | Passed |
| Changed-slice Ruff check | Passed |
| Changed-slice Pyright | `0 errors, 0 warnings, 0 informations` |
| `git diff --check` | Passed |

No credentials, activation, PAPER/LIVE operation, real OANDA request, or
broker mutation was used. Other original findings were outside R001 scope and
were not reassessed.

## Validation receipt

- **Verdict:** `PASS`
- **CRITICAL findings:** None
- **IMPORTANT findings:** None
- **MINOR findings:** None
- **Capital safety:** No capital-capable operation was authorized or performed.
- **Files changed by this validation:** this `VALIDATION.md` only.
