# T001 — Implement the OANDA Practice open Trade inventory

- **Status:** `DONE_WITH_CONCERNS`
- **Workstream:** `paper-01c-oanda-practice-open-trade-inventory`
- **Depends on:** developer approval and GIT START on `solo/paper-01c-oanda-practice-open-trade-inventory` (complete).

## Assignment

Implement only the approved `PLAN.md` slice: validate the explicit Practice account through the existing 01A identity seam, issue the narrow read-only `/v3/accounts/{accountID}/openTrades` request, and return an immutable normalized OANDA provider open-Trade inventory.

## Required constraints

- Keep provider Trades separate from Atlas `Trade`, `Position`, `Order`, `Fill`, `Direction`, and `FinancialPositionState` semantics.
- Preserve unsupported provider instruments as provider-native strings; do not filter them or expand the Atlas `Instrument` enum.
- Preserve signed finite `currentUnits` as a provider fact; do not derive an Atlas Position or absolute quantity.
- Normalize only the approved Trade fields and response provenance; ignore detailed accounting, client-extension, and dependent/protection Order fields.
- Fail closed and sanitize credentials/raw bodies for malformed Trades, missing/invalid fields, duplicate or conflicting IDs, invalid JSON, provider failures, and exhausted retries.
- Return a successful explicit empty inventory for a valid empty `trades` list.
- Reject all duplicate provider Trade IDs; do not merge or first-win. Normalize output deterministically by numeric provider Trade ID.
- Do not compare PAPER 01B summary counts or transaction IDs to this independent read, and do not persist any inventory or cursor.
- Do not add persistence, API/UI, runtime, Risk, execution, reconciliation, activation, broker mutation, or generalized broker architecture. Stop as `BLOCKED` if the approved outcome crosses those boundaries.

## Required evidence

- Account validation followed by exact Practice `GET /v3/accounts/{configuredAccountID}/openTrades`, headers, and one first-attempt open-Trades request.
- Successful normalization of multiple provider Trades, an unsupported instrument, positive/negative signed units, adverse/zero/positive P/L, stable order, provenance, and explicit empty inventory.
- Fail-closed coverage for malformed objects/IDs/instruments/prices/timestamps/units/states/P&L/provenance, zero units, duplicate/conflicting IDs, invalid JSON, provider/transport failures, retries, and sanitized errors.
- Proof that extra detailed Trade/protection fields are ignored and no Atlas financial state or forbidden endpoint is introduced.
- Focused OANDA tests, targeted Ruff/Pyright, and the non-integration/non-external suite recorded in Worker Evidence.

## Worker Evidence

Implemented the approved read-only OANDA Practice open-Trades slice:

- added `OandaPracticeOpenTrade` and `OandaPracticeOpenTradeInventory` as frozen,
  slotted provider-specific values;
- added `OandaPracticeOpenTradeReader` with bounded sanitized retries and exact
  `GET /v3/accounts/{configuredAccountID}/openTrades` headers/path;
- added the settings-facing helper that validates the configured account through
  the existing `/summary` identity seam before the independent `/openTrades` read;
- normalized only the approved provider fields, preserved signed units and
  provider-native instruments, rejected duplicates/invalid states/invalid fields,
  sorted by numeric provider Trade ID, and accepted explicit empty inventories;
- exported only the new OANDA open-Trades contracts, reader, normalization error,
  and helper;
- added deterministic MockTransport coverage for request sequencing, successful
  normalization, unsupported instruments, signed units, P/L values, ordering,
  empty inventory, ignored provider/protection details, malformed data, duplicate
  IDs, provenance, retries, transport/provider failures, and sanitization.

Files changed by BUILD:

- `backend/integrations/oanda/trades.py`
- `backend/integrations/oanda/__init__.py`
- `backend/tests/integrations/test_oanda_trades.py`

Checks and evidence:

- `uv run pytest backend/tests/integrations/test_oanda_trades.py backend/tests/integrations/test_oanda_account.py backend/tests/integrations/test_oanda_source.py` — **116 passed**;
- `uv run pytest -m "not integration and not external"` — **503 passed, 4 skipped, 88 deselected**;
- targeted `uv run ruff format --check ...` — **passed**;
- targeted `uv run ruff check ...` — **passed**;
- targeted `uv run pyright ...` — **0 errors, 0 warnings, 0 informations**;
- `git diff --check` — **passed**.

Concerns:

- repository-wide Ruff format/check and Pyright were also run but report
  pre-existing findings in unrelated files; no such findings occur in the changed
  OANDA module or tests. No database, API/UI, runtime, Risk, execution,
  reconciliation, or persistence behavior was introduced.
