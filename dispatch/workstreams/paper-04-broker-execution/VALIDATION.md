# VALIDATION — PAPER 04 Broker Execution

- **Status:** PASS
- **Role:** VALIDATE
- **Workstream:** `paper-04-broker-execution`
- **Branch:** `solo/paper-04-broker-execution`
- **Base:** `53c6b229d6d5081e7853163d7e70952d14c33d61` (`main` and `HEAD`)
- **Receipt:** Complete and immutable independent validation receipt.

## Scope reviewed

Independently read the canonical `PLAN.md`, frozen `ARCHITECTURE.md`, all five
completed BUILD receipts (T001–T005), and the complete working-tree diff against
the base. The diff is limited to the OANDA execution/capability adapter, PAPER
execution contracts/composition, focused deterministic tests, and SoloFlow
operational/workstream receipts. No historical execution, Risk/PAPER 03,
Strategy, persistence, migration, runtime, API/UI, frontend, or LIVE files were
changed.

## Checks and evidence

- Focused new PAPER/OANDA matrix: **59 passed**.
- Focused OANDA/PAPER/Risk/historical execution regression suite:
  **554 passed, 1 skipped**.
- Broad backend suite `pytest -m "not integration and not external"`:
  **919 passed, 4 skipped, 88 deselected**. Only pre-existing warning output
  (Starlette/httpx deprecation and unregistered `price_analysis` mark).
- Changed Python files: `ruff format --check` **passed**; `ruff check`
  **passed**; `pyright` **0 errors, 0 warnings**.
- Tracked and untracked changed-file `git diff --check`: **passed**.
- All mutation evidence used `httpx.MockTransport`, deterministic fakes, and
  fixed/unit test credentials. No credentialed or external OANDA request was
  made.

## Acceptance matrix

All 40 PLAN acceptance criteria independently pass. Evidence covers:

- Practice-only EUR/USD IMMEDIATE OPEN_LONG/OPEN_SHORT scope; fresh PAPER 03
  Risk composition exactly once; stale evaluation rejection; coherent single
  account snapshot; non-MT4, GSLO, flatness, pending-order, identity/frontier,
  precision, and quantity gates before POST.
- Exact provider translation: unsigned provider-neutral quantity, OANDA-only
  signed units, MARKET/FOK/OPEN_ONLY, exact Risk `priceBound`, exact ordinary
  GTC `stopLossOnFill`, deterministic correlation, no target-on-entry, and no
  rounding.
- One entry POST at most; no POST retry after transport uncertainty, 429/5xx,
  malformed response, duplicate ID, or readback uncertainty. HTTP success alone
  does not establish a Fill; complete FOK quantity and `tradeOpened` are
  required, with `TradeOpen.price` as authority and bound/geometry/risk checks.
- Fill-proven protection remains distinct from entry uncertainty. Stop
  confirmation gates target derivation; target uses actual Fill plus immutable
  Strategy R-multiple methodology; unrepresentable targets are not rounded.
  Dependent protection is one exact GTC Take Profit mutation containing only
  `takeProfit`, never retries, and requires final Trade/Stop/Take Profit
  readback before `FILLED_PROTECTED`.
- `REJECTED`, `CANCELLED`, `UNKNOWN`, `FILLED_PROTECTION_INCOMPLETE`, and
  `FILLED_PROTECTED` remain distinct with bounded diagnostics/provenance and
  stable attempt correlation. No raw provider payload, unbounded provider text,
  or credential enters result evidence.
- Historical Experiment Order/Fill semantics and all excluded persistence,
  runtime, activation, API/UI, migration, and LIVE behavior remain isolated.

## Capital-boundary safety

No real broker mutation, PAPER activation, LIVE behavior, or credentials were
used during BUILD or this validation. The deterministic mutation seams prove
non-retrying POST/PUT behavior and bounded readback only. The residual
snapshot-to-mutation race, durable attempt ownership, and unknown/protection
reconciliation remain the explicitly documented PAPER 05 boundary.

## Findings

None. Validation passes with no unresolved acceptance, safety, regression,
tooling, or isolation finding.
