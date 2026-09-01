# VALIDATION — OANDA Read-only Observation Infrastructure Refactor

## Status

`PASS`

## Role

`VALIDATE`

Independent validation completed against the frozen PLAN, ARCHITECTURE, T001
receipt, implementation/test diff, and required checks.

## Validation boundary

- CWD verified as `/Users/vike/Desktop/atlas` and repository root verified.
- Branch verified as `solo/oanda-read-only-observation-infrastructure-refactor`.
- No application, test, fixture, or implementation files were changed by
  VALIDATE.
- The branch diff is limited to the approved OANDA observation files/tests,
  dispatch bookkeeping, and the workstream evidence directory. No forbidden
  boundary directory is changed.

## Independent evidence

### Required checks

- Focused OANDA regression suite, including `test_oanda_source.py`: **253
  passed**.
- `uv run pytest -m "not integration and not external"`: **640 passed, 4
  skipped, 88 deselected**, with 4 pre-existing warnings.
- Targeted Ruff format check: **10 files already formatted**.
- Targeted Ruff lint: **passed**.
- Targeted Pyright: **0 errors, 0 warnings, 0 informations**.
- `git diff --check`: **passed**; the four untracked added implementation/test
  files were additionally checked with `git diff --no-index --check` and had
  no whitespace errors.

### Request seam and exact request behavior

- `request.py` centralizes only bounded timeout validation/construction,
  token preflight, authenticated GET, response classification, retry, JSON
  decoding, and safe error formatting. It has no closed observation registry;
  `error_subject` is only interpolated into safe messages.
- Constructor bounds and construction are exact: connect `(0, 30]`, read
  `(0, 120]`, and `httpx.Timeout(read=read, connect=connect,
  write=connect, pool=connect)`.
- `get_json` validates the token before owned-client creation or network
  activity. Account validation separately performs token validation before
  configured account-ID validation, preserving precedence.
- Owner modules retain the exact local paths and quoting:
  `/v3/accounts/{quoted account_id}/summary`, `/openTrades`, and
  `/openPositions`. The requester always performs GET against the fixed
  `https://api-fxpractice.oanda.com` URL, sends exactly `Authorization` and
  `Accept-Datetime-Format: RFC3339`, and supplies no query parameters. Focused
  request/account/Trade/Position tests assert URL, method, headers, path, and
  query behavior.
- Injected clients receive the per-request timeout, remain open on success and
  failure, and take precedence over a separately supplied transport. Without
  an injected client, one owned client is created per read and closed exactly
  once through the requester's `finally` path. Independent runtime checks
  confirmed timeout values, owned closure, injected-client ownership, and
  transport precedence.
- Successful JSON is returned as `Any` after one `response.json()` call. The
  requester does not classify object shape; each owner retains its
  `isinstance(payload, dict)` check and domain-specific non-object error.
- Invalid JSON is non-retried and produces the existing subject-specific
  `OandaRequestError`; provider bodies and tokens are not surfaced.

### Retry, status, metadata, and sanitization

- The shared policy preserves three maximum GET attempts, transport fallback
  sleeps `0.25` then `0.5`, and transient `408`, `429`, and `5xx` retries.
- Numeric `Retry-After` accepts finite nonnegative values, caps at `30.0`, and
  falls back for missing, malformed, zero, negative, and non-finite values.
  Future timezone-aware HTTP dates are used and capped at `30.0`; naive and
  past dates fall back. Focused tests cover each required boundary.
- `401/403` are immediate `OandaAuthError`; `400/404` are immediate rejected
  requests; other non-2xx statuses fail immediately; transient exhaustion and
  transport exhaustion preserve status/attempt metadata and exact sanitized
  wording. No provider response body or secret-bearing transport exception
  text escapes.
- Focused tests assert same-GET retry paths, request counts, fallback/capped
  sleeps, status codes, attempt counts, and exact messages for account, open
  Trades, and open Positions.

### Primitive and domain ownership

- `primitives.py` contains only OANDA provider-format parsers. Transaction IDs
  use exact `str` plus full-match `[0-9]+` semantics and preserve leading
  zeroes. Decimals require exact `str`, parse to finite `Decimal`, and impose
  no sign/zero policy. Instruments use exact `str` plus full-match
  `[^\s_]+_[^\s_]+` semantics and remain unchanged provider strings.
- Account, Trade, and Position owners catch `OandaPrimitiveError` and retain
  their existing domain-specific normalization errors/messages. Local
  positive Trade-ID, nonzero-unit, timestamp/state, Position side-sign,
  average-price, both-zero, ordering, duplicate, and account summary rules
  remain in their owning modules.
- Trade inventory accepts distinct Trades sharing an instrument: the existing
  permutation test uses distinct IDs `100` and `2` with the same default
  `USD_CAD` instrument, while the duplicate regression rejects exact repeated
  IDs. An additional independent runtime check accepted IDs `101` and `105`
  on `EUR_USD` and rejected duplicate ID `101`.
- Position inventories still reject only duplicate provider instruments and
  preserve independent long/short sides, zero-side representation, active-side
  average-price requirements, both-nonzero visibility, and both-zero failure.
- Settings-facing Trade and Position helpers still bind `/summary` first,
  then perform the independent observation; no caching, reconciliation, or
  atomicity claim was introduced.

### Boundary and scope checks

- `source.py` has no diff from the base commit and contains no use of
  `OandaObservationRequester`; historical query/window/diagnostic behavior is
  therefore outside this seam.
- `backend/integrations/oanda/__init__.py` has no diff from the base commit;
  new requester/primitive symbols are not package exports.
- AST inspection found no imports from the forbidden Atlas trading,
  execution, persistence, risk, runtime, API, or frontend boundaries in the
  OANDA integration package.
- No new endpoint, non-GET method, provider mutation, persistence, runtime,
  Risk, execution, reconciliation, Order, PAPER 01E, LIVE, or financial-state
  behavior is present.

## Findings

None.

## Concerns

The four full-suite warnings are pre-existing and unrelated to this
workstream. No capital-capable or credentialed external behavior was used.
