# T003 — Non-retrying OANDA entry mutation + normalization/readback

- **Status:** DONE
- **Role:** BUILD
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Depends on:** T002

## Assignment

Create a separate OANDA Practice write requester for the exact approved entry
mutation endpoint, with bounded timeouts, authenticated JSON, sanitized
diagnostics, and exactly one POST attempt. Normalize matching Fill, FOK cancel,
broker reject, and entry UNKNOWN outcomes from bounded provider facts. Implement
the bounded original-correlation readback sequence after uncertain entry
submission without cancellation, repair, or resubmission. Add MockTransport and
normalized fixture tests proving no POST retry.

## Acceptance

- Existing observation requester remains GET-only.
- POST transport uncertainty, 429/5xx, malformed possible-submission responses, and duplicate IDs never cause a second POST.
- Valid Fill requires exact matching create/fill/tradeOpened/FOK/OPEN_ONLY/full quantity and uses `tradeOpened.price`.
- Bound and actual-risk invariants are enforced; cancel/reject/unknown remain distinct.
- Readback is bounded and not-found/PENDING/unrecognized/readback failure remain UNKNOWN.

## Worker evidence

Implemented the T003 entry-mutation slice without changing the observation
requester, Strategy/Risk semantics, persistence, runtime, API/UI, or historical
execution:

- Added `OandaPracticeMutationRequester` as a separate authenticated Practice
  POST boundary with bounded timeouts, sanitized failures, and exactly one
  request attempt; transient statuses and transport uncertainty never retry.
- Added the public `OandaPracticeEntryMutation` seam and deterministic
  correlation-based single-attempt guard. Entry responses normalize only
  bounded broker facts into the existing `PaperExecutionResult` contract.
- Validated matching MARKET/FOK/OPEN_ONLY create/fill facts, full signed
  quantity, `tradeOpened.price`, bound/stop geometry, actual initial risk, FOK
  cancellation, broker rejection, and explicit UNKNOWN outcomes.
- Added bounded original-client-ID readback for FILLED/CANCELLED/PENDING and
  unrecognized states. Readback uses the existing GET-only safe requester and
  performs no cancellation, repair, or resubmission.
- Added deterministic `httpx.MockTransport` and fake-reader public-seam tests
  covering POST shape/authentication, no retry, Fill/CANCELLED/REJECTED/
  UNKNOWN normalization, invariant failure, and readback bounds.

## Checks

- `uv run pytest backend/tests/integrations/test_oanda_entry_mutation.py -q` — **15 passed**.
- Focused T001/T002/OANDA/PAPER/Risk/historical execution regression suite — **166 passed**.
- `uv run pytest -m "not integration and not external" -q` — **903 passed, 4 skipped, 88 deselected**; only existing warning output.
- Focused `ruff format --check`, `ruff check`, `pyright`, and `git diff --check` — **passed**.
- No real OANDA requests, credentials, broker mutations, persistence, or runtime activation performed.

## Concerns

- Inherited T001/T002 application changes and SoloFlow operational changes in
  the worktree were preserved and not edited by T003.
- Protection completion, dependent Take Profit mutation, and composition remain
  owned by T004/T005.
