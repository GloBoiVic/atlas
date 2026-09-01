# VALIDATION — PAPER 01C OANDA Practice Open Trade Inventory

- **Status:** `FAIL`
- **Workstream:** `paper-01c-oanda-practice-open-trade-inventory`
- **Branch:** `solo/paper-01c-oanda-practice-open-trade-inventory`
- **Role:** `VALIDATE`
- **Original task:** `T001`

## Validation assignment

Independently verify the approved `PLAN.md` acceptance criteria, the BUILD receipt,
the implementation and tests, and the explicitly bounded provider-only scope.

Verify at minimum:

- exact `/openTrades` method, path, headers, account-validation sequencing, and
  first-attempt request count;
- independent identity and open-Trades observations with no summary reconciliation;
- immutable field sets, provider-native instruments, signed units, accepted states,
  duplicate rejection, deterministic numeric ordering, empty inventory, and
  transaction provenance;
- malformed data, provider/transport failures, bounded retries, and sanitization;
- ignored detailed/protection fields and absence of forbidden financial-domain,
  persistence, API/UI, runtime, Risk, execution, reconciliation, activation, and
  later-PAPER behavior;
- focused tests, targeted quality checks, and `git diff --check`.

## Developer instruction

Use the focused OANDA validation command below rather than the broad
non-integration/non-external suite, whose unrelated historical-data tests are
known to be long-running:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_trades.py \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_source.py
```

## Evidence

### Independent environment and scope check

- CWD and repository root verified as `/Users/vike/Desktop/atlas`.
- Branch verified as `solo/paper-01c-oanda-practice-open-trade-inventory`.
- BUILD changes are limited to the planned OANDA integration module, exports,
  focused tests, and workstream state/evidence files.
- No persistence, schema/migration, API/UI, runtime, Risk, execution,
  reconciliation, activation, mutation, or capital-capable behavior was found.

### Acceptance verification

- The settings helper calls `bind_oanda_practice_account(...)` first, then
  `OandaPracticeOpenTradeReader.read()`. The focused sequencing test observed
  exactly `/summary` followed by one authenticated `GET` to
  `/v3/accounts/{configuredAccountID}/openTrades`, with no query parameters and
  `Accept-Datetime-Format: RFC3339`.
- The reader uses frozen, slotted provider-specific identity/inventory values,
  retains exactly the approved Trade fields, preserves provider-native
  instruments and signed finite units, accepts `OPEN` and
  `CLOSE_WHEN_TRADEABLE`, and returns `()` for a valid empty list.
- Duplicate IDs, malformed retained fields, invalid provenance, invalid JSON,
  authorization/provider failures, transport failures, and exhausted retries
  fail closed. Retry tests confirm bounded retries of only the same `GET`, and
  error tests confirm credentials and response bodies are not exposed.
- Extra accounting, client-extension, and dependent/protection Order fields are
  ignored. No Atlas financial-domain state or forbidden endpoint is introduced,
  and no PAPER 01B count/frontier reconciliation is performed.

### Checks

- Focused OANDA tests: the instructed command — **116 passed**.
- Targeted Ruff format check — **passed**.
- Targeted Ruff lint check — **passed**.
- Targeted Pyright — **0 errors, 0 warnings, 0 informations**.
- `git diff --check` and no-index whitespace checks for the new files —
  **passed**.
- The BUILD receipt reports the non-integration/non-external suite passed
  (**503 passed, 4 skipped, 88 deselected**). It also reports repository-wide
  Ruff/Pyright findings confined to unrelated pre-existing files; per the
  developer instruction, that long-running broad suite was not rerun here.

## Findings

### IMPORTANT V-001 — numeric ordering is not permutation-invariant for leading-zero IDs

`_positive_integer(...)` accepts both `"2"` and `"02"` as valid positive-integer
Trade IDs. `_trade_id_sort_key(...)` strips leading zeroes and returns the same
sort key for both, while `OandaPracticeOpenTradeInventory` uses stable sorting.
Consequently, the same valid two-Trade response in opposite provider array
orders produces `("2", "02")` versus `("02", "2")`, violating acceptance
criterion 8's provider-order-independent normalized equality. This was reproduced
against the current implementation. No implementation files were changed by
VALIDATE.

Remediation must either reject non-canonical leading-zero Trade IDs (if that is
the provider contract) or add a deterministic raw-ID tie-breaker and explicit
duplicate semantics, with a permutation test.

## Conclusion

The focused implementation and quality checks pass, and the approved provider-only
scope is otherwise satisfied. Validation remains **FAIL** until V-001 is resolved
and its regression test is added.
