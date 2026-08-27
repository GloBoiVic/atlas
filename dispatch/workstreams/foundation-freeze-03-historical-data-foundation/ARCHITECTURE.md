# Foundation Freeze 03 — Authoritative V2 Historical-Data Contract

Status: `FROZEN — developer approved`

## 1. Authority and scope

V2 is the sole authoritative historical-data path for the initial slice: EUR/USD,
OANDA Practice as the provider, UTC, and completed observations only. It exists to
serve an Experiment with two different products:

* **Analytical product:** provider-native OANDA M15 **MID** candles. These are the
  Strategy's 15-minute inputs and are never constructed from M1 in the authoritative
  Experiment path.
* **Execution product:** provider-native OANDA M1 **BID and ASK** observations. These
  are the executable sides used by the simulation after a decision frontier.

The products, required ranges, missing ranges, provider calls, validation, and
progress are planned independently. A request is successful only when both products
are valid for their respective requirements. The older feature text saying “M1 base,
derive M15” is superseded for V2; it remains historical documentation, not a contract.

## 2. Request contract and range semantics

An accepted load request contains a StrategyVersion, `trading_start`, and
`trading_end`, all timezone-aware UTC instants, with `trading_end > trading_start` and
15-minute alignment. `trading_end` is also the exclusive end of both products. The
provider range convention is half-open `[start, end)`. No request may extend beyond
the latest completed-minute frontier.

The planner derives, without coupling the products:

1. Start with a wall-clock estimate, then extend the analytical range backward until
   it contains `required_completed_analytical_bars` valid completed native M15 MID
   bars before `trading_start`;
2. `execution_range = [trading_start, trading_end)`.

`required_completed_analytical_bars` is the immutable StrategyVersion requirement.
Warm-up M15 bars may
initialize Strategy state but cannot produce exposure or TradeIntents before
`trading_start`. If a future Strategy declares a different execution lookback, that
requirement belongs to the execution product and must not be smuggled into analytical
warm-up. Weekend/session closures and missing intervals do not count toward this
completed-bar count. The final snapshot records the exact ordered analytical context
membership; it never fabricates context to satisfy the count.

For each product, local coverage is inspected by its exact provider, resolution, and
component key. Only missing expected session-open intervals are sent to OANDA; a fully
covered product causes zero OANDA requests. Existing valid observations are reused.
The planner must produce a deterministic, sorted, coalesced list of disjoint windows
and may contain any number of bounded provider chunks. Missing coverage spans and
provider request chunks are distinct: large plans are processed in bounded batches
with durable progress and resume, never rejected because of request-window count.

## 3. Provider and canonical observation contract

The OANDA adapter owns provider symbols, request parameters, pagination, rate limits,
and request-window limits. V2 must use native requests: M15/MID for analysis and
M1/BID+ASK for execution. OANDA-specific objects do not cross into Strategy or
Experiment code. Each provider call is a bounded half-open window; no unbounded
one-year request is permitted. Current initial adapter bounds are 60,000 minutes for
M15 and 4,000 minutes for M1; changing either bound is a contract/configuration
change requiring benchmark and test evidence.

Normalize every returned observation to canonical UTC before validation and persistence.
Persist provider provenance, resolution, component, interval, OHLC/price values, source
request identity, completion state, and content fingerprint. Only `complete == true`
observations enter canonical membership. Duplicate identical observations are
idempotent; conflicting observations for the same identity are a validation failure,
not “last write wins”. Existing observations referenced by an immutable Snapshot are
never overwritten. Freeze 03 does not implement provider correction/refresh; if added
later, corrections must create immutable/versioned content. Financial values use
Decimal/NUMERIC.

No forward-fill, interpolation, synthetic candle, constant spread, or M1→M15
replacement is allowed. An unexpected missing constituent or provider closure is
reported explicitly. Expected Forex closure is not a fabricated observation. Native
M15 alignment must be on UTC quarter-hour boundaries; M1 alignment must be on UTC
minute boundaries.

## 4. Durable progress and resume

`historical_data_load_requests` is the durable command record, with one active request
at most (`PENDING` or `RUNNING`). It records the exact request ranges, product/window
progress, bounded counts, coverage/validation facts, and allowlisted failure category
and code. It never stores credentials, headers, provider bodies, raw exception text, or
diagnostics containing secrets.

Provider I/O occurs outside database transactions. After each successfully validated
window, canonical observations and their product coverage are committed atomically;
then a short transaction records that window's durable progress. Progress may lag the
observation commit by one boundary; coverage, never progress JSON alone, decides
whether the request is complete.

On retry/resume, recompute local coverage and plan only remaining missing windows for
each product. Never reissue a completed window merely because progress was stale, and
never infer completion from a partial transaction. A process interruption leaves the
request inspectable and resumable by an explicit coordinator action; it must not claim
success or create a second active request. If the implementation retains startup
failure of abandoned rows, that is incompatible with V2 resume and must be replaced
by an explicit safe-resume transition before implementation approval.

Terminal states are:

* `COMPLETED`: both products pass coverage/integrity and an immutable snapshot is
  created or deterministically reused.
* `FAILED`: no further provider I/O occurs for the attempt; failure facts identify
  what happened, what was persisted, and whether new Experiment creation is blocked.

Unknown provider outcome, persistence failure, conflicting data, invalid timestamps,
incomplete candles needed for coverage, unexpected gaps, and frontier violations are
blocking failures. Planning may fail only for malformed inputs or violated invariants
such as an unbounded internal window, never because a valid research range needs many
bounded provider chunks. A network timeout is never converted into an empty result or
assumed success. Persisted canonical data from successful earlier windows remains
inspectable and reusable on resume.

## 5. DatasetSnapshot and determinism

A completed V2 request creates an immutable DatasetSnapshot describing the exact
analytical native-M15-MID membership and execution native-M1-BID/ASK membership,
coverage bounds, warm-up requirement, UTC alignment, provider contracts, integrity
diagnostics, and source/content fingerprint. Snapshot membership is an explicit
immutable view; later provider corrections do not mutate it.

The fingerprint is a deterministic hash of canonical snapshot metadata plus sorted
membership identities and content fingerprints. Same inputs and same persisted
observations produce the same fingerprint and reusable snapshot identity. Any
correction, membership change, contract/version change, or relevant metadata change
produces a new fingerprint. A completed Experiment retains its original snapshot and
can never silently see corrected data.

Experiment validation must require a V2 snapshot whose analytical and execution
products both cover the requested range and whose warm-up is present. Strategy sees
only completed analytical M15 MID bars through the no-lookahead frontier. Execution
simulation sees only completed BID/ASK observations at or after the decision frontier;
the bar consumed to make a decision cannot also be used as post-decision execution
data.

## 6. Stale-path and compatibility decisions

V2 is the only path allowed to create snapshots used by new Experiments. Legacy
`load_missing`, one-component/shared-range planning, M1-derived M15 snapshots, and
V1 snapshot creation are quarantined from new Experiment creation and must not be
silently routed into V2. They may remain as read-only migration/diagnostic code until
all existing references are removed.

Existing V1 snapshots and completed Experiments remain readable and immutable; they
are not rewritten, backfilled, or upgraded in place. New V2 persistence uses explicit
product/resolution/component and contract-version metadata. If old rows lack the
metadata needed to prove native M15/M1 provenance, they are incompatible with V2 and
must be reloaded. Alembic migrations preserve canonical observations and snapshots;
cleanup may remove only unreachable stale code/paths after callers and tests prove no
new authoritative use. No destructive historical-data deletion is part of Freeze 03.

## 7. Examples

**Valid:** A one-year request needs 20 completed M15 bars before trading start, has 8
missing M15 spans and 40 missing M1 spans. The planner may split those spans into any
number of bounded provider chunks, commits each, resumes after interruption from
remaining coverage, and completes only after both products validate.

**Valid:** All analytical M15 MID and execution M1 BID/ASK coverage already exists.
Coverage validation creates/reuses a deterministic snapshot and makes zero OANDA
calls.

**Invalid:** M15 is absent but M1 is present, so Atlas aggregates M1 to “fill” M15.
V2 rejects the request; it does not fabricate analytical history.

**Invalid:** BID is present but ASK is absent for an execution minute, or a returned
candle is incomplete. The relevant product is incomplete and Experiment creation is
blocked.

**Boundary:** `[10:00, 10:15)` includes the 10:00 native M15 candle and excludes
10:15; a decision at 10:15 cannot consume an execution observation before 10:15.
The exact required number of completed native analytical bars before `trading_start`
is included as warm-up context; wall-clock subtraction is only an initial acquisition
estimate. `trading_end` is excluded.

**Boundary:** A weekend/expected-closure interval is excluded from expected coverage
according to the session policy, but any actual observation during an unavailable
session is an integrity anomaly. It is never repaired by filling the closure.

## 8. Required tests and benchmark evidence

Implementation must provide deterministic tests for:

 * independent analytical/execution range and missing-window planning, completed-bar
  warm-up across closures/gaps, UTC half-open boundaries, frontier rejection, and
  arbitrary-size plans processed in bounded chunks;
* OANDA native M15 MID and native M1 BID/ASK request parameters, pagination/window
  limits, completed filtering, UTC normalization, malformed/conflicting responses,
  and redacted failure facts;
* missing-only behavior, zero provider calls when fully covered, duplicate and
  out-of-order idempotency, Decimal preservation, expected closure classification,
  unexpected gaps, incomplete product rejection, and explicit no-fabrication;
* per-window atomic persistence/progress, progress lag tolerance, interruption,
  resume-from-remaining-coverage, no duplicate active request, terminal failure, and
  unknown-outcome blocking;
* immutable snapshot membership, fingerprint stability/change, native provenance,
  V1 exclusion, Experiment coverage validation, warm-up no-exposure, no-lookahead,
  and post-decision BID/ASK execution semantics;
* migration compatibility: old snapshots/Experiments remain readable and immutable,
  metadata-deficient rows cannot masquerade as V2, and stale paths cannot create new
  V2 snapshots.

Benchmark evidence must report, using fixed deterministic fixtures and the same
environment: fresh one-month, fresh one-year, repeat covered one-year, and
interrupted/resumed one-year scenarios. Each report includes M15 provider calls/time,
M1 provider calls/time, persistence time, coverage/planning time,
snapshot/fingerprint time, total time, observations inserted/reused, and repeat-call
counts. Deterministic fixture evidence is required. Credentialed OANDA Practice
evidence is also required when available for fresh one-month, fresh one-year, and
repeat covered one-year; unavailable real-provider evidence is reported as blocked,
not replaced by fixture timing. Evidence must demonstrate bounded
memory/transactions and be attached to the implementation task receipt; timings are
evidence, not a correctness substitute.
