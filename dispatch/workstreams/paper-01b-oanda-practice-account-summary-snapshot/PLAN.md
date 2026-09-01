# PLAN — PAPER 01B OANDA Practice Account Summary Snapshot

## Workstream state

- **Workstream:** `paper-01b-oanda-practice-account-summary-snapshot`
- **Outcome:** one explicit, validated OANDA Practice account → one successful read-only `/summary` response → immutable normalized identity plus broker-reported account-summary facts.
- **Classification:** `Feature`. This is a bounded provider-facing capability with financial facts, but it is read-only, non-capital, non-persistent, and does not alter Risk, runtime, execution, or broker authority. `ARCHITECTURE.md` is not required.
- **Phase:** `COMPLETED`; merge approved and fast-forward merged into `main`.
- **Base:** `main` at `16022db0e0fed9bd2d61dc0cfa4fa9a60dd1c575`.
- **Branch:** `solo/paper-01b-oanda-practice-account-summary-snapshot`.
- **Task:** `T001` — `DONE`; implementation and task-level evidence are complete.
- **Next action:** none; workstream closed.
- **Inherited working-tree state:** `.gitignore` was modified before this workstream, rechecked during GIT START and GIT END, and remained untouched and excluded from all commits.

## Current 01A foundation and exact gap

PAPER 01A already provides:

- `Settings.oanda_api_token` as `SecretStr`, fixed OANDA Practice base URL, bounded connect/read timeouts, and explicit `Settings.oanda_account_id` validation using OANDA's four-part AccountID shape;
- `OandaPracticeAccountValidator.validate()` and `bind_oanda_practice_account()`;
- one logical authenticated read of `GET /v3/accounts/{configuredAccountID}/summary` for the configured account, using bounded safe retry when required;
- fail-closed response JSON/schema handling, exact returned-account-ID matching, USD base-currency validation, and the immutable five-field `OandaPracticeAccountIdentity` (`provider`, `environment`, `provider_account_id`, `alias`, `base_currency`);
- no persistence, API/UI, runtime, Risk, execution, reconciliation, or capital-capable behavior.

The gap is that the same successful account-summary response is currently reduced to identity only.

PAPER 01B adds a narrow result contract for selected broker-reported account-summary facts without adding another provider endpoint, another account-selection mechanism, or a second logical `/summary` read for callers requesting the snapshot.

The existing PAPER 01A identity contract remains independently valid. Adding PAPER 01B must not make `validate()` depend on the presence or validity of 01B-only financial, count, or transaction-summary fields.

## Provider contract and retained snapshot

OANDA documents the account-summary endpoint as returning:

- `account`: an `AccountSummary`;
- top-level `lastTransactionID`: the ID of the most recent Transaction created for the account.

`AccountSummary` is a summary representation and does not provide the full detailed pending Order, open Trade, and Position representations exposed by the full-account endpoint.

OANDA represents account-unit financial values as decimal strings, counts as integers, and `TransactionID` as a string representation of a numerical OANDA-assigned transaction identifier.

Provider references consulted:

- OANDA Account summary endpoint;
- OANDA `AccountSummary` definition;
- OANDA primitive definitions;
- OANDA `TransactionID` definition.

Retain exactly the existing identity plus these nine facts:

| Snapshot field              | Provider field                | Why this slice retains it                                                                                                     |
| --------------------------- | ----------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| `balance: Decimal`          | `account.balance`             | Current broker-reported account balance is a primary summary fact.                                                            |
| `nav: Decimal`              | `account.NAV`                 | Current broker-reported net asset value is a primary summary fact; it is observed and is not sent to Risk.                    |
| `unrealized_pl: Decimal`    | `account.unrealizedPL`        | Preserves current broker-reported unrealized P/L without reconstructing Trades or Positions.                                  |
| `margin_used: Decimal`      | `account.marginUsed`          | Preserves current broker-reported margin usage.                                                                               |
| `margin_available: Decimal` | `account.marginAvailable`     | Preserves current broker-reported available margin, including financially concerning values.                                  |
| `open_trade_count: int`     | `account.openTradeCount`      | Preserves the broker-reported number of open Trades without fetching detailed Trades.                                         |
| `open_position_count: int`  | `account.openPositionCount`   | Preserves the broker-reported number of open Positions without reconstructing Atlas Positions.                                |
| `pending_order_count: int`  | `account.pendingOrderCount`   | Preserves the broker-reported number of pending Orders without fetching detailed Orders.                                      |
| `last_transaction_id: str`  | top-level `lastTransactionID` | Preserves transaction provenance for the state observed in this response. It is not a reconciliation cursor or durable state. |

`identity: OandaPracticeAccountIdentity` is nested in the snapshot so the existing provider, environment, exact configured account, alias, and USD base currency remain attached to the observed summary state.

`OandaPracticeAccountSummarySnapshot` will be immutable and slotted and will expose no raw provider payload or detailed broker entities.

Balance, NAV, and unrealized P/L are retained as independently broker-reported facts. Atlas does not replace them with locally derived equivalents and does not introduce financial-policy interpretation into normalization.

Finite negative or zero financial values remain observable where permitted by the provider representation. The snapshot must not reject a broker fact merely because a later Risk or activation policy may consider that fact unsafe.

All other account-summary fields remain outside this slice, including:

- account creation/user/time fields;
- margin-rate and hedging configuration;
- position value;
- margin-closeout fields;
- margin-call fields;
- withdrawal limit;
- realized/lifetime P/L;
- financing;
- commission;
- dividend adjustments;
- guaranteed-execution fees;
- any detailed Orders, Trades, or Positions that may exist in other provider representations.

No full-account endpoint is added.

### Transaction provenance consistency

OANDA's `AccountSummary` also contains `account.lastTransactionID` while the endpoint response contains a top-level `lastTransactionID`.

The top-level value is the canonical value exposed by `OandaPracticeAccountSummarySnapshot`, but the nested value must not be silently ignored if it contradicts the top-level endpoint provenance.

For summary normalization:

- both values must satisfy the OANDA `TransactionID` representation when present as required provider fields;
- the nested and top-level transaction IDs must agree;
- disagreement is contradictory provider state and fails closed;
- no transaction ID is persisted or advanced.

This consistency check does not turn the transaction ID into a reconciliation cursor.

## Normalization and failure contract

Evolve the existing OANDA-only account seam rather than add another HTTP client or generalized broker abstraction.

The implementation is expected to provide:

- a summary-reading entrypoint returning `OandaPracticeAccountSummarySnapshot`;
- a public `read_oanda_practice_account_summary(settings, *, client/transport)` helper using the existing injected-client/transport test seam;
- shared request/configuration behavior with PAPER 01A;
- separate identity normalization and summary normalization so PAPER 01A does not acquire PAPER 01B field requirements.

### Preserve PAPER 01A semantics

`OandaPracticeAccountValidator.validate()` and `bind_oanda_practice_account()` must continue to return exactly `OandaPracticeAccountIdentity`.

They may share:

- configuration validation;
- the `/summary` request implementation;
- timeout/retry behavior;
- sanitized provider failure handling;
- identity normalization.

They must not require all PAPER 01B financial, count, or transaction-summary fields to be valid merely to establish the existing PAPER 01A identity contract.

In particular, do not implement PAPER 01A compatibility by making:

```text
validate()
→ read_summary()
→ snapshot.identity
```

if that causes `validate()` to reject responses solely because an 01B-only summary field is malformed or absent.

Reuse the provider read seam while preserving distinct normalization contracts.

### Summary read behavior

A caller requesting the account summary snapshot performs:

```text
configuration validation
→ one logical authenticated /summary read
→ identity normalization
→ summary normalization
→ immutable snapshot
```

On a successful first HTTP attempt, this produces exactly one provider GET.

Existing bounded safe retry may repeat that same GET after transient transport/provider failure. Retry attempts are not a second logical account-summary read.

Do not implement:

```text
bind account
→ successful /summary read

then

read account summary
→ second successful /summary read
```

inside the snapshot workflow.

### Financial values

Required financial fields must be provider decimal strings parsed to finite `Decimal` values.

Reject:

- missing required fields;
- non-string financial values;
- invalid decimal text;
- `NaN`;
- positive infinity;
- negative infinity.

Do not reject a finite value solely because it is financially adverse.

Examples that remain observable rather than becoming normalization failures include:

- negative finite unrealized P/L;
- finite negative NAV if reported by the provider;
- zero NAV;
- zero margin available;
- nonzero margin used.

PAPER 01B does not introduce Risk thresholds, capital-safety decisions, or locally derived account accounting.

### Counts

Required count fields must be exact JSON integers.

Reject:

- booleans;
- strings;
- floats;
- null;
- negative integers.

Zero and positive counts are valid broker facts.

A nonzero count must not cause:

- detailed Trade retrieval;
- detailed Position retrieval;
- detailed Order retrieval;
- Atlas `Position` reconstruction;
- reconciliation;
- a Risk decision.

### Transaction ID

The top-level `lastTransactionID` is the snapshot's canonical transaction-provenance value.

Transaction IDs used by this snapshot must be:

- strings;
- non-empty;
- composed only of the numerical characters required by OANDA's documented TransactionID representation.

Reject malformed transaction IDs and contradictory top-level/nested transaction provenance.

`last_transaction_id` means only:

> the most recent broker Transaction ID reported with this observed account-summary response.

It is not:

- a reconciliation cursor;
- a durable recovery marker;
- an Account Changes cursor;
- a replay position;
- permission to advance broker state;
- permission to create exposure.

### Existing failures

Identity mismatch, unsupported base currency, malformed account structure, malformed JSON, deterministic provider rejection, transport failure, and exhausted bounded safe retries continue to produce no result and sanitized failures.

No credential or raw provider response body may enter an exception or log message.

## Persistence decision

**Persistence is not required.**

The PAPER 01B outcome is a fresh read and immutable in-memory normalized value.

No:

- restart recovery;
- audit-history persistence;
- reconciliation cursor;
- `TradingAccount`;
- Deployment;
- broker-state lifecycle

is required to satisfy this slice.

The snapshot and `last_transaction_id` must not be written to:

- the database;
- a cache;
- a file;
- durable runtime state.

If BUILD discovers a concrete requirement for persistence, it must stop as `BLOCKED` and return for re-scoping rather than add persistence opportunistically.

## Implementation seams

Expected changes are limited to:

| File                                               | Planned change                                                                                                                                                                                                                                                    |
| -------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `backend/integrations/oanda/account.py`            | Add the immutable summary snapshot, narrow financial/count/transaction normalization, summary-reading entrypoint, shared one-read request seam, and separate identity/summary normalization needed to preserve PAPER 01A behavior.                                |
| `backend/integrations/oanda/__init__.py`           | Export only the new snapshot contract and `read_oanda_practice_account_summary` entrypoint.                                                                                                                                                                       |
| `backend/tests/integrations/test_oanda_account.py` | Add deterministic `httpx.MockTransport` coverage for summary normalization, first-attempt one-GET behavior, retry semantics, transaction-provenance consistency, adverse-but-valid facts, malformed fields, ignored provider fields, and PAPER 01A compatibility. |

No changes are expected to:

```text
backend/config.py
.env.example
backend/persistence/
backend/risk/
backend/runtime/
backend/domain/trading.py
backend/execution/
backend/api/
frontend/
backend/integrations/oanda/source.py
```

No schema or migration is expected.

If implementation demonstrates that a required change crosses one of these boundaries, BUILD must stop as `BLOCKED` and return for re-scoping rather than expanding this plan.

## Acceptance criteria

1. A valid explicit OANDA Practice account summary returns one immutable `OandaPracticeAccountSummarySnapshot` containing exactly:

   - the existing account identity;
   - balance;
   - NAV;
   - unrealized P/L;
   - margin used;
   - margin available;
   - open Trade count;
   - open Position count;
   - pending Order count;
   - last transaction ID.

2. Required financial values are normalized from provider decimal strings into finite `Decimal` values. Required counts are exact non-negative integers. Required transaction provenance is a valid numerical OANDA TransactionID string.

3. Identity and all summary facts for a snapshot are normalized from the same successful `/v3/accounts/{configuredAccountID}/summary` response. A first-attempt successful snapshot read performs exactly one authenticated GET. Existing bounded safe retries may repeat the same GET after transient failure but no second logical account-summary read is introduced.

4. The snapshot path never calls:

   - `/v3/accounts` account enumeration;
   - full-account retrieval;
   - detailed Order endpoints;
   - detailed Trade endpoints;
   - detailed Position endpoints;
   - Account Changes;
   - transaction-history endpoints;
   - mutating endpoints.

5. Existing `validate()` and `bind_oanda_practice_account()` PAPER 01A callers continue to return the same `OandaPracticeAccountIdentity` and preserve their existing configuration, selection, request, retry, sanitization, identity-matching, USD, and fail-closed semantics.

6. PAPER 01A identity validation is not made dependent on PAPER 01B-only financial, count, or transaction-summary normalization. Malformation of an 01B-only field does not silently redefine the previously closed 01A identity contract.

7. Missing or malformed required summary fields, invalid numeric representations including non-finite values, malformed or negative counts, malformed transaction IDs, contradictory top-level/nested transaction IDs, invalid JSON, provider failures, and identity/currency mismatch produce no snapshot and sanitized failure.

8. Finite but adverse broker facts remain observable. Negative or zero financial facts that are representable by the provider and nonzero Trade/Position/Order counts do not become normalization failures solely because later Risk or activation logic may reject them.

9. Extra provider fields and detailed broker representations are not exposed by the snapshot. No Atlas Position, Trade, Order, Risk state, reconciliation state, or durable cursor is constructed.

10. No persistence, runtime, API/UI, Risk, execution, activation, Deployment, or capital-capable behavior is introduced.

## Validation strategy

BUILD will first run the focused account and preserved historical OANDA tests:

```bash
uv run pytest \
  backend/tests/integrations/test_oanda_account.py \
  backend/tests/integrations/test_oanda_source.py
```

Then run targeted Ruff format/lint and Pyright for changed integration and test modules.

Then run:

```bash
uv run pytest -m "not integration and not external"
```

Independent VALIDATE will inspect:

- the exact implementation diff;
- the exact request method/path;
- first-attempt request count;
- bounded retry behavior;
- absence of a second logical `/summary` read;
- PAPER 01A compatibility;
- separation of identity and summary normalization;
- finite Decimal normalization;
- exact non-negative count normalization;
- transaction-ID representation and duplicate-provenance consistency;
- adverse-but-valid fact handling;
- provider-field isolation;
- sanitization;
- all forbidden-scope boundaries.

VALIDATE will rerun:

- focused OANDA account tests;
- directly relevant historical OANDA regression tests;
- appropriate targeted backend quality gates;
- the non-integration/non-external suite;
- `git diff --check`.

No database or Alembic gate is required because persistence is unchanged.

No credentialed external OANDA request is required for acceptance.

## Explicitly deferred / out of scope

This workstream does not implement or authorize:

- full-account retrieval;
- account enumeration;
- detailed pending Orders;
- detailed open Trades;
- detailed Positions;
- Atlas Position reconstruction;
- Atlas Trade or Order correlation;
- transaction history;
- Account Changes;
- transaction replay;
- reconciliation;
- reconciliation cursor persistence;
- account-summary persistence;
- `TradingAccount`;
- Deployment;
- PAPER activation;
- runtime coordinator;
- runtime ownership;
- START/STOP controls;
- frontend work;
- FastAPI expansion;
- live market data;
- Strategy evaluation;
- Strategy-state persistence;
- Risk changes;
- broker NAV/equity wiring into Risk;
- position eligibility;
- order sizing;
- executable quotes;
- Order creation or submission;
- Fill handling;
- broker protection;
- generalized broker/account architecture;
- PAPER 01C or later behavior;
- LIVE.

If any of these appears necessary during BUILD, stop and surface the requirement rather than expanding the workstream.
