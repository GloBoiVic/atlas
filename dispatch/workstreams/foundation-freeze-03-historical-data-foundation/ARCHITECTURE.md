# Foundation Freeze 03 — Authoritative V2 Historical-Data Contract

Status: `FROZEN — telemetry/progress and performance evidence contract added`

## 1. Authority and scope

V2 is the sole authoritative historical-data path for the initial slice: EUR/USD,
OANDA Practice as the provider, UTC, and completed observations only. It exists to
serve an Experiment with two different products:

- **Analytical product:** provider-native OANDA M15 **MID** candles. These are the
  Strategy's 15-minute inputs and are never constructed from M1 in the authoritative
  Experiment path.
- **Execution product:** provider-native OANDA M1 **BID and ASK** observations. These
  are the executable sides used by the simulation after a decision frontier.

The products, required ranges, missing ranges, provider calls, validation, and
progress are planned independently. **Acquisition coverage is not observation
continuity.** Acquisition coverage means a bounded provider window was successfully
requested, its result was durably classified (including a valid zero-candle result),
and it is reusable without re-querying. Observation continuity describes observations
actually returned inside that window. M1 may be sparse; Atlas never fills, carries
forward, or otherwise fabricates observations. A request is successful only when both
products are valid for their respective requirements. The older feature text saying “M1 base,
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
component key. Missing expected open-session intervals identify needed calendar ranges;
deterministic coalescing may include intervening closure time. Only those coalesced
missing ranges are sent to OANDA; a fully acquired product causes zero OANDA requests.
A successful M1 BID/ASK window may
contain zero or sparse returned minutes and is still acquired data; repeat requests
must not re-query it merely because continuity is sparse. Existing valid observations
and successful-window classifications are reused. Provider failure, timeout,
malformed response, or unknown outcome is not successful acquisition and remains
retryable/blocking according to the failure rules below.
The planner must produce a deterministic, sorted, coalesced list of disjoint windows.
Successful acquisition windows form a set of half-open intervals, not just exact
request keys: their union covers later requests, including overlaps and subranges.
Planning subtracts that union deterministically (sort by start/end, merge touching or
overlapping intervals, then scan left-to-right) and requests only the uncovered
remainder. Failed or unknown windows add no coverage and remain retryable; they are
never treated as successful empty responses.
The plan may contain any number of bounded provider chunks. Missing coverage spans and
provider request chunks are distinct: large plans are processed in bounded batches
with durable progress and resume, never rejected because of request-window count.

Session policy is not a provider-request partitioning policy. It determines which
intervals are expected observations and how returned data is validated, but it must not
split an otherwise valid bounded calendar range at a weekend, holiday, or other
closure. Request chunks are split only by the configured provider bound, product
resolution/component, and deterministic acquisition-coverage subtraction. A request
may therefore contain closure time; closure intervals contribute no expected
observation and do not make a successful provider response a failure.

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
replacement is allowed. BID and ASK are independent required constituents: neither
side may be fabricated when the other is absent. Expected Forex closure is not an
acquisition failure and is not a fabricated observation. Native M15 MID remains
strict: every required completed analytical bar and warm-up/context bar must be
present and complete; unexpected M15 gaps are analytical validation failures. M1
BID/ASK is different: sparse open-session observations are valid acquired execution
data when their containing provider window succeeded. An absent, incomplete, or
missing-constituent M1 observation is explicit; execution must not invent a price.
Native M15 alignment must be on UTC quarter-hour boundaries; M1 alignment must be on
UTC minute boundaries. A fully absent expected open M1 minute (neither BID nor ASK)
is valid sparse execution data only when its containing M1 BID+ASK acquisition coverage
is successful. Exactly one present required constituent is an invalid one-sided absence,
even when its window succeeded. No missing observation is repaired or fabricated.

### T013 gap classification (2025 calendar-year diagnosis)

The 1,293 gaps are classified against the unchanged V2 session policy and canonical
rows, not treated as a reason to weaken analytical coverage:

| Dimension      | Classification                                | Count / evidence                                                                 |
| -------------- | --------------------------------------------- | -------------------------------------------------------------------------------- |
| Product        | native M15 MID                                | 0 gaps reported by recomputed T013 coverage; M15 remains strict                  |
| Product        | native M1 BID/ASK                             | 1,293 expected-session minute gaps, in 927 scattered runs                        |
| Session        | expected closure                              | 0; T013 found no closure anomalies                                               |
| Session        | open-session absence                          | 1,293; includes 1,076 minutes in the post-rollover 17:00 local hour              |
| M1 shape       | fully absent minute (neither BID nor ASK row) | 1,293 by the canonical gap definition                                            |
| M1 shape       | missing BID or ASK constituent only           | 0 observed; remains a separately reported anomaly                                |
| Window outcome | provider failure/unknown                      | 0 in the sampled diagnosis (38 runs: HTTP 200, one attempt, zero target candles) |
| Window outcome | successful sparse/zero response               | confirmed for those 38 sampled runs                                              |
| Window outcome | not yet individually classified               | 889 of the 927 runs; not silently counted as success or failure                  |

Widened six-target samples returned surrounding candles but no target candle, including
with `price=MBA`, supporting provider sparsity rather than boundary omission or
BID/ASK-only normalization. These counts are diagnostic facts, not permission to
label an uninspected timeout successful. Every window must persist
`SUCCESS_EMPTY_OR_SPARSE`, `PROVIDER_FAILURE`, or `UNKNOWN_OUTCOME` (and its returned
observations), so the complete gap report is reproducible by product, closure,
constituent shape, and outcome.

## 4. Exact gap and acquisition classification

Every expected interval is classified independently by product, session policy,
observation shape, and acquisition outcome:

| Classification                         | Exact condition                                                                                                        | Effect                                                                         |
| -------------------------------------- | ---------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| `EXPECTED_CLOSURE`                     | Session policy says the interval is closed and no observation is required                                              | Excluded from expected coverage; not a failure                                 |
| `M15_MISSING_NATIVE_COMPLETED`         | Expected open native M15/MID interval has no complete native M15 MID member                                            | Blocking analytical gap; acquisition success never substitutes for the candle  |
| `M1_FULLY_ABSENT_ACQUIRED`             | Expected open M1 minute has neither BID nor ASK and its containing M1 BID+ASK acquisition union covers it successfully | Valid sparse execution absence; preserve explicit no-fill/unavailable behavior |
| `M1_MISSING_CONSTITUENT`               | Exactly one of BID/ASK is present, or one required constituent is incomplete                                           | Invalid execution data; blocking validation anomaly                            |
| `M1_UNACQUIRED`                        | Expected open M1 minute is not covered by any successful acquisition window                                            | Missing acquisition; fetch the deterministic remainder                         |
| `UNEXPECTED_OBSERVATION`               | Any observation occurs in a policy closure or outside the requested/native range                                       | Integrity failure; never repaired                                              |
| `PROVIDER_FAILURE` / `UNKNOWN_OUTCOME` | Window failed, timed out, was malformed, or its result is uncertain                                                    | No acquisition coverage; retryable but blocking until resolved                 |

Classification is precedence-ordered for reporting: closure policy first, observation
shape second, successful-window union third, with provider outcome/failure facts always
retained. Native M15 is strict: every expected open completed M15/MID bar in analytical
warm-up and trading range must be present and complete. A successful M15 acquisition
window, including an empty response, is evidence only that the provider was queried; it
never substitutes for a missing expected native M15 MID.

## 5. Durable progress and resume

`historical_data_load_requests` is the durable command record, with one active request
at most (`PENDING` or `RUNNING`). It records the exact request ranges, product/window
progress, bounded counts, coverage/validation facts, and allowlisted failure category
and code. It never stores credentials, headers, provider bodies, raw exception text, or
diagnostics containing secrets.

Provider I/O occurs outside database transactions. After each provider request, canonical observations and the acquisition-window outcome
are committed atomically. Product integrity/continuity is evaluated separately according
to the M15/M1 rules.

On retry/resume, recompute local coverage and plan only the deterministic remainder of
the successful acquisition-window union for each product. Never reissue a successfully
acquired M1 window merely because it has sparse or zero observations, and never reissue
a completed window merely because
progress was stale. Reissue only a provider-failed/unknown window or an explicitly
authorized correction operation, and never infer completion from a partial transaction.
A process interruption leaves the
request inspectable and resumable by an explicit coordinator action; it must not claim
success or create a second active request. If the implementation retains startup
failure of abandoned rows, that is incompatible with V2 resume and must be replaced
by an explicit safe-resume transition before implementation approval.

Terminal states are:

- `COMPLETED`: both products pass coverage/integrity and an immutable snapshot is
  created or deterministically reused.
- `FAILED`: no further provider I/O occurs for the attempt; failure facts identify
  what happened, what was persisted, and whether new Experiment creation is blocked.

Unknown provider outcome, persistence failure, conflicting data, invalid timestamps,
incomplete candles needed for coverage, unexpected gaps, and frontier violations are
blocking failures. Planning may fail only for malformed inputs or violated invariants
such as an unbounded internal window, never because a valid research range needs many
bounded provider chunks. A network timeout is never converted into an empty result or
assumed success. Persisted canonical data from successful earlier windows remains
inspectable and reusable on resume.

## 6. DatasetSnapshot and determinism

The fingerprint is a deterministic hash of canonical snapshot metadata, the
canonical successful M1 BID/ASK acquisition-coverage union, and sorted exact
membership identities/content fingerprints.

At DatasetSnapshot creation, successful M1 BID/ASK acquisition coverage is
intersected with the required execution range, sorted, and touching or
overlapping intervals are merged. That canonical coverage union is persisted
as immutable DatasetSnapshot provenance.

Raw provider request-window identities, pagination shape, and request chunk
boundaries are operational/audit facts only and are not part of DatasetSnapshot
identity.

Therefore identical contracts, requested range, exact observations, and
canonical acquisition coverage produce the same fingerprint even if OANDA was
queried using different bounded chunks. Any correction, sparse-membership
change, canonical acquisition-coverage change, contract/version change, or
relevant metadata change produces a new fingerprint. A completed Experiment
retains its original snapshot and can never silently see corrected data.

Experiment validation must require a V2 snapshot whose required analytical
native M15 MID bars and warm-up/context are complete for the requested range.
It validates exact sparse M1 membership against the successful M1 BID/ASK
acquisition coverage pinned to that immutable DatasetSnapshot. It must not
consult current/global acquisition-window records to reinterpret an existing
Snapshot. It never requires a fabricated continuous M1 calendar.

## 7. Stale-path and compatibility decisions

V2 is the only path allowed to create snapshots used by new Experiments. Legacy
`load_missing`, one-component/shared-range planning, M1-derived M15 snapshots, and
V1 snapshot creation are quarantined from new Experiment creation and must not be
silently routed into V2. They may remain as read-only migration/diagnostic code until
all existing references are removed.

`load_v2_incremental` is not an authoritative compatibility path and must be removed
or bypassed. Warm-up extension always invokes canonical `load_v2` over the extended
range. Canonical persistence and reuse plan both native products from durable current
observations plus successful acquisition-window union; a prior snapshot is metadata,
never a source of analytical or execution rows. The extended load reuses the covered
prefix without provider calls through this missing-only path, then creates a new
immutable snapshot.

Existing V1 snapshots and completed Experiments remain readable and immutable; they
are not rewritten, backfilled, or upgraded in place. New V2 persistence uses explicit
product/resolution/component and contract-version metadata. If old rows lack the
metadata needed to prove native M15/M1 provenance, they are incompatible with V2 and
must be reloaded. Alembic migrations preserve canonical observations and snapshots;
cleanup may remove only unreachable stale code/paths after callers and tests prove no
new authoritative use. No destructive historical-data deletion is part of Freeze 03.

## 8. Examples

**Valid:** A one-year request needs 20 completed M15 bars before trading start, has 8
missing M15 spans and 40 missing M1 spans. The planner may split those spans into any
number of bounded provider chunks, commits each, resumes after interruption from
remaining coverage, and completes only after both products validate.

**Valid:** All analytical M15 MID and execution M1 BID/ASK coverage already exists.
Coverage validation creates/reuses a deterministic snapshot and makes zero OANDA
calls.

**Invalid:** M15 is absent but M1 is present, so Atlas aggregates M1 to “fill” M15.
V2 rejects the request; it does not fabricate analytical history.

**Valid:** A successful M1 BID/ASK provider window returns no candle at an open-session
minute. The window is durably acquired and is not re-requested; exact sparse snapshot
membership preserves the absence, and execution cannot fill from that minute.

**Valid:** Successful `[10:00, 10:10)` and `[10:05, 10:15)` M1 windows cover a later
overlapping/subrange request by union. Deterministic subtraction requests only the
uncovered remainder, with no duplicate call.

**Invalid:** BID is present but ASK is absent for an execution minute, a returned
candle is incomplete, or a fully absent minute is outside successful acquisition union.
The relevant fact is explicit and Experiment validation blocks; no spread or price is
invented. A failed/unknown overlapping window adds no coverage.

**Invalid:** Native M15 MID is absent while its provider window returned an empty
successful response. Acquisition is recorded, but the analytical gap remains blocking;
M1 data cannot replace it.

**Boundary:** In `[10:00, 10:15)`, a fully absent 10:07 M1 minute is valid only if a
successful M1 window covers `[10:07, 10:08)`; a BID-only 10:08 minute is invalid even
if the same successful window covers it.

**Boundary:** `[10:00, 10:15)` includes the 10:00 native M15 candle and excludes
10:15; a decision at 10:15 cannot consume an execution observation before 10:15.
The exact required number of completed native analytical bars before `trading_start`
is included as warm-up context; wall-clock subtraction is only an initial acquisition
estimate. `trading_end` is excluded.

**Boundary:** A weekend/expected-closure interval is excluded from expected coverage
according to the session policy, but any actual observation during an unavailable
session is an integrity anomaly. It is never repaired by filling the closure.

## 9. Required tests and benchmark evidence

Implementation must provide deterministic tests for:

- independent analytical/execution range and missing-window planning, completed-bar
  warm-up across closures/gaps, UTC half-open boundaries, frontier rejection, and
  arbitrary-size plans processed in bounded chunks;
- OANDA native M15 MID and native M1 BID/ASK request parameters, pagination/window
  limits, completed filtering, UTC normalization, malformed/conflicting responses,
  and redacted failure facts;
  - successful empty/sparse M1 windows are reusable with zero repeat calls; fully
    absent acquired minutes are valid, one-sided minutes are invalid; failed or
    unknown windows are retryable/blocking and never mistaken for successful empties;
  - successful acquisition-window union/subrange/overlap reuse, deterministic interval
    subtraction (including touching and nested intervals), and canonical `load_v2`
    warm-up extension for both M15 and M1 without `load_v2_incremental`;
  - missing-only behavior, zero provider calls when fully acquired, duplicate and
    out-of-order idempotency, Decimal preservation, expected closure classification,
    unexpected gaps, incomplete product rejection, and explicit no-fabrication;
- per-window atomic persistence/progress, progress lag tolerance, interruption,
  resume-from-remaining-coverage, no duplicate active request, terminal failure, and
  unknown-outcome blocking;
  - immutable exact sparse-M1 membership, acquisition-window metadata, fingerprint
    stability/change for membership and window outcomes, native provenance, V1
    exclusion, Experiment coverage validation, warm-up no-exposure, no-lookahead,
    and post-decision BID/ASK execution semantics;
  - the T013 1,293-gap fixture/report classified by M15/M1, closure/open-session,
    fully-absent versus missing-constituent, and successful versus failed/unknown
    window outcome, with fully-absent acquired gaps valid and one-sided gaps blocking;
  - snapshot and Experiment validation for native-M15 absence despite successful
    acquisition, sparse fully-absent M1 minutes inside successful union coverage,
    one-sided M1 absence, unacquired remainder, and failed/unknown retryability;
  - migration compatibility: old snapshots/Experiments remain readable and immutable,
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

## 10. Final performance remediation contract

This section narrows implementation mechanics only; it does not change V2 product,
sparsity, provenance, fingerprint, validation, resume, or immutability semantics above.
The relevant bound is the number of observations/windows in the request, not the
number of provider chunks. No implementation may retain a whole requested range in a
Python list, tuple, set, JSON progress field, or callback closure merely to make a
later operation convenient.

### 10.1 Progress and transactions

After each successfully validated provider window, the existing atomic observation
commit and separate short progress transaction remain mandatory. A progress callback
and its durable projection must follow the exact contract in section 11. It must be
O(1) per window: current product/window, bounded counters, and bounded status/error
facts are allowed; unbounded `fetched_ranges`, `committed_ranges`, gap arrays, or
per-observation payloads are not. If a range summary is exposed, it is a bounded
count/byte-size or canonical interval summary with an explicitly enforced limit,
never the complete history of windows.

Progress must not call whole-range coverage validation after every window. Coverage
updates are incremental from the committed window/result (or are performed once at a
defined product boundary); they must not scan all expected minutes or all persisted
bars per callback. A progress notification may lag the latest observation commit, as
already specified, and must never become the resume authority. Provider I/O remains
outside transactions, and a crash between the two commits remains resumable from
durable bars plus successful acquisition-window union.

### 10.2 Bounded PostgreSQL reads and writes

Repository reads used for planning, coverage, snapshot construction, and repeat
planning must be ordered, server-side streamed or keyset/chunk paginated reads with a
fixed implementation batch size. `.all()`/`tuple(...)` over a request-sized query and
Python dictionaries/sets keyed by every minute are prohibited. A read API may yield
canonical rows or compact counters/interval state, but it must preserve the exact
ordered result and half-open filters (`start_time >= start`, `start_time < end`).
Each batch is released before the next batch; transaction lifetime is bounded to the
read operation and never spans provider I/O. Planning may keep only the current merged
interval frontier and bounded diagnostics while scanning.

Snapshot membership insertion is likewise batched (or an equivalent PostgreSQL
set-based insert) and commits within the snapshot's existing atomic immutability
boundary. It must not first materialize all analytical or execution membership rows,
all gaps, or all source bars in Python. A failed batch leaves no partially visible
completed snapshot; a completed snapshot has exactly the same rows and sequence values
as the prior unbounded implementation would have produced.

### 10.3 Deterministic streaming fingerprint

V2 fingerprint input is a canonical ordered stream, hashed incrementally with SHA-256.
The order is fixed and independent of query arrival order, provider chunk boundaries,
database page size, and batch size: canonical metadata/header first; analytical
membership by `(start_time, sequence)`; execution membership by
`(start_time, price_component, sequence)`; then gaps by their canonical ordered
identity. Each emitted record uses the existing canonical JSON representation and
content/observation fingerprints. The implementation must reject duplicate or
out-of-order records rather than silently changing order, or explicitly sort only
inside a bounded database `ORDER BY` stream; it must not call `sorted()` on the full
iterable. Batch boundaries and retry/resume boundaries must not affect the digest.

Acquisition coverage is part of the V2 header/provenance stream as the sorted, merged,
touching-inclusive half-open union clipped to the execution range. Raw request-window
IDs and chunk boundaries remain excluded from identity. The same logical metadata,
coverage union, memberships, and gaps therefore produce byte-identical fingerprints;
any logical member/content/coverage/contract change produces a different one.

### 10.4 Coverage-first repeat planning

Repeat planning first reads the successful acquisition-window union for the exact
provider/resolution/component/product key, merges it deterministically, and subtracts
it from the requested range.

For M1 BID/ASK, successful acquisition coverage is sufficient to avoid observation
scans for the purpose of deciding whether provider I/O is required. Only the uncovered
remainder may cause provider calls. Do not scan the full M1 observation calendar to
decide whether an already acquired sparse/zero window is reusable. A fully covered
request makes zero provider calls even when many M1 minutes have no observations.

For M15 MID, successful acquisition coverage avoids unnecessary provider re-query,
but Atlas must still stream and validate the persisted native M15 membership. A missing
required M15 candle remains a blocking analytical gap even when its provider window
was successfully acquired. Failed/unknown windows are never
included in the union.

After coverage proves no acquisition is needed, snapshot construction may stream the
exact current native memberships for validation/fingerprinting/insertion; it must not
reinterpret the immutable membership of an existing snapshot from current global
coverage. Repeat planning and snapshot creation remain separate from the authoritative
Experiment read path, and a prior snapshot remains metadata only.

### 10.5 Resource budget and benchmark protocol

The implementation must have bounded RSS and finite progress time on the target Intel
Mac with 8 GB RAM. For the genuine full-calendar-year fixture, peak RSS must remain
under 1 GiB above the idle test-process baseline, no single request-sized Python
collection may be present, and planning, coverage, persistence, and fingerprinting
must each be linear in rows/windows (no repeated whole-range scan). The benchmark must
fail/report a concern if RSS grows with retained rows rather than the fixed batch
bound, or if a covered-repeat run performs provider I/O. These are engineering
guardrails, not permission to weaken validation or omit rows.

Run each scenario in a fresh process with the same schema, Python version, database
configuration, fixture, batch size, and Intel Mac power/network conditions: fresh
one-month, genuine fresh one-year, covered-repeat one-year, and interrupted/resumed
one-year. Record baseline and peak RSS, elapsed time, per-window and per-product
provider calls/time, persistence time, planning/coverage time, snapshot time,
fingerprint time, total time, rows inserted/reused, progress payload maximum size,
maximum batch size, and repeat calls. Run deterministic fixture evidence first; run
credentialed OANDA Practice evidence separately when available and label unavailable
evidence `BLOCKED` rather than substituting fixture timings. Compare the fingerprint,
membership counts/order, coverage classifications, and terminal state between fresh,
resumed, and repeat runs. A benchmark is not passing evidence unless correctness and
resource measurements are both captured.

The evidence report must use the section 11 names and units. In particular, it must
show expected and completed provider requests separately for M15 and M1 before any
provider I/O, average and p95 provider/request and persistence/batch durations,
coverage/validation, snapshot-membership, fingerprint, and total elapsed timings,
inserted rows per second, baseline/peak RSS, and the maximum serialized telemetry
payload. A scalar shared `completed_units`, a null `total_units`, or a request count
inferred from rows is not acceptable evidence.

### 10.6 Required performance regressions and examples

Required regressions include:

- a multi-window load whose progress callback is invoked after every window without
  growing payload size or invoking whole-range coverage; callback count is O(windows);
- repository planning and snapshot reads over a full-year fixture use bounded batches,
  preserve UTC half-open order, and never materialize all rows;
- streamed fingerprinting equals the known digest for multiple batch sizes, input
  insertion orders, overlapping acquisition windows, and resumed versus fresh loads;
- membership insertion rolls back atomically on a failed batch and produces exact
  immutable ordered membership on success;
- successful empty/sparse coverage, nested/touching/overlapping windows, and a fully
  covered repeat make zero provider calls without a full-calendar observation scan;
- a failed/unknown window remains retryable, a crash after observation commit but
  before progress does not duplicate work, and a completed snapshot/Experiment cannot
  be altered by later ingestion;
- the genuine full-year benchmark enforces the RSS/batch/progress-payload guardrails
  and reports all required timing/call metrics.

**Valid:** 10,000 successful one-minute windows cover the execution range. Repeat
planning merges their union and makes zero provider calls while snapshot members are
streamed in fixed batches and the digest is unchanged by batch size.

**Valid:** A callback after each of 1,000 windows reports only current-window data and
bounded counters; its payload remains bounded and a crash after window 417 resumes
from durable coverage rather than replaying successful windows.

**Invalid:** Each callback calls `_coverage(start, end)`, or appends every prior range;
each snapshot call uses `.all()`/`tuple(...)` for a full year; or fingerprinting sorts
and retains all members. These violate the contract even if final data is correct.

**Boundary:** Successful `[10:00,10:10)` and `[10:10,10:20)` windows merge into one
`[10:00,10:20)` union; `[10:20,10:21)` is the only remainder. A failed overlapping
window contributes no coverage. A sparse fully absent minute inside the successful
union remains valid and is not fetched or fabricated.

**Boundary:** Batch size 1 and batch size 10,000 must yield identical ordered rows,
coverage classifications, and fingerprint; memory is allowed to differ only within
the fixed batch bound, never with total year-row count.

## 11. Frozen telemetry, progress, and safe reuse contract

This section is implementation authority for the next telemetry implementation and
supersedes any older progress shape in application code, API examples, or benchmark
harnesses. Telemetry is an inspectable operational projection, not a source of market
data truth, coverage truth, snapshot identity, or resume authority. Durable canonical
observations plus successful acquisition-window records remain the resume authority.

### 11.1 Product keys and progress meaning

Telemetry uses exactly two product keys:

| Key | Role | Native provider contract |
| --- | --- | --- |
| `m15` | analytical | OANDA M15, `MID` |
| `m1` | execution | OANDA M1, `BID` + `ASK` |

The public progress object has this fixed shape (additional arbitrary keys are not
allowed):

```json
{
  "schema": "ATLAS_HISTORICAL_PROGRESS_V1",
  "phase": "PLANNING",
  "unit": "provider_request",
  "completed_units": {"m15": 0, "m1": 0},
  "total_units": {"m15": 8, "m1": 40},
  "products": {
    "m15": {"expected_requests": 8, "completed_requests": 0},
    "m1": {"expected_requests": 40, "completed_requests": 0}
  }
}
```

`completed_units[p]` is the number of bounded provider request windows for product
`p` whose response was validated and whose canonical observations **and successful
acquisition-window outcome** were durably committed. A successful empty or sparse M1
response counts as one completed request. It is a request count, never a bar, minute,
observation-row, byte, HTTP-attempt, or database-transaction count. A provider failure,
timeout, malformed response, or unknown outcome increments none of these counters.

`total_units[p]` is the number of bounded provider request windows in the deterministic
missing-coverage plan for product `p`, after successful-window-union subtraction and
coalescing, for the current `plan_generation`. It is known and durably written for both
products before the first provider call of that generation. It includes only provider
windows that may be issued; already covered windows are not counted as new work. The
corresponding `products[p].expected_requests` and `products[p].completed_requests` are
the same integers, not independently maintained values. At a fully covered repeat,
both products are `0/0` and provider calls are zero.

The coordinator must plan both products before acquisition begins so that neither
product has `total_units = null` or an absent expected count. A warm-up extension or
explicit resume creates a new monotonically increasing `plan_generation` and writes
the new per-product totals before its next provider call. Counts from an earlier
generation are retained only as bounded aggregate evidence (`provider_calls_total`);
they are not copied into the new generation's `completed_units`. Replanning may
reduce expected work through durable union reuse, but it may not mark a failed or
unknown window complete. Progress percentages, if displayed, are `completed_units /
total_units` for the same product and generation; `0/0` displays `covered`, not 100%.

The scalar legacy meanings are forbidden: `completed_units` and `total_units` must
never be a shared scalar, `total_units` must never be null for an acquired generation,
and database rows/observations must never be used as a proxy for completed provider
requests. The legacy range arrays remain empty compatibility fields if the schema
requires them; they are not telemetry and are never read for resume.

### 11.2 Bounded, redacted phase telemetry

The durable progress projection contains only fixed schema fields: fixed enums,
booleans, UTC timestamps, integer counters, durations in integer milliseconds, byte
counts, and the two product keys. It is capped at **8 KiB serialized UTF-8**; the
writer rejects any over-cap update before persistence rather than allowing unbounded
growth. It may
contain the current `plan_generation`, current product, the latest bounded window
summary, and aggregate counters. It must not contain a window history, all expected
intervals, gap arrays, provider response data, OHLC/prices, URLs, query strings,
headers, credentials/tokens, account identifiers, raw exception text, stack traces,
or arbitrary provider/user strings. Failure facts use the existing allowlisted
category/code/detail contract and are redacted before storage.

Allowed phase enum values are `PLANNING`, `ACQUIRING`, `VALIDATING`,
`SNAPSHOT_MEMBERSHIP`, `FINGERPRINTING`, `FINALIZING`, `COMPLETED`, and `FAILED`.
Each phase emits at most one aggregate start/end record plus O(1) per-window progress
updates. `PLANNING` reports, per product, `expected_requests`,
`already_covered_window_count`, `uncovered_span_count`, and `planning_elapsed_ms`;
it never serializes the spans. `ACQUIRING` reports the current product's
`completed_units`, `total_units`, `provider_calls_total`, `inserted_rows`,
`reactivated_rows`, `unchanged_rows`, and only the latest window's bounded start/end
summary. All other phases report their fixed aggregate timing and bounded row/batch
counters. The full shape and cap are test-enforced; a callback must not invoke a
whole-range coverage scan or retain prior reports.

Progress may lag the latest observation/window commit and may be absent after a crash.
It is status/audit information only. A crash between durable commits is resolved by
recomputing canonical rows and successful acquisition-window union, never by trusting
the last progress payload.

### 11.3 Required timing and resource metrics

The terminal telemetry report contains all of the following, with `*_ms` as integer
milliseconds and RSS as integer bytes. Each product is reported separately under
`m15` and `m1`, plus an `overall` aggregate where applicable:

```json
{
  "timing": {
    "planning": {"elapsed_ms": 12},
    "provider": {
      "m15": {"calls": 8, "elapsed_ms": 1200, "average_ms": 150, "p95_ms": 220},
      "m1": {"calls": 40, "elapsed_ms": 8000, "average_ms": 200, "p95_ms": 310}
    },
    "persistence": {
      "m15": {"batches": 8, "elapsed_ms": 600, "average_batch_ms": 75, "p95_batch_ms": 110, "inserted_rows": 2400, "rows_per_second": 4000},
      "m1": {"batches": 40, "elapsed_ms": 4000, "average_batch_ms": 100, "p95_batch_ms": 160, "inserted_rows": 72000, "rows_per_second": 18000}
    },
    "validation": {"elapsed_ms": 90, "valid": true},
    "snapshot_membership": {"elapsed_ms": 300, "rows": 74400, "batches": 30},
    "fingerprinting": {"elapsed_ms": 80, "records_hashed": 74400},
    "total_elapsed_ms": 14260
  },
  "rss": {"baseline_bytes": 70000000, "peak_bytes": 180000000, "delta_bytes": 110000000}
}
```

`provider.*.calls` counts provider request windows, including successful empty/sparse
responses and terminal failed/unknown calls; `completed_units` counts only successful
ones. The provider elapsed time is the sum of per-window wall time around the OANDA
adapter call, including adapter retries within that window and excluding persistence.
Persistence elapsed time is measured around each committed canonical observation batch,
separately for M15 and M1; snapshot-membership insertion is reported only in its own
phase and is not silently folded into M15/M1 persistence. `average_ms` is elapsed/count
when count is nonzero, otherwise null; `p95_ms` is also null when count is zero.
`rows_per_second` is newly inserted canonical
observation rows divided by that product's persistence seconds; reactivated and
unchanged rows are not numerator rows. A zero-row/zero-time metric is null, never
infinity or a fabricated rate.

For bounded deterministic p95, each duration stream uses the fixed 17-bucket
logarithmic histogram `[1, 2, 4, ..., 2^16]` milliseconds plus explicit zero and
overflow buckets. `p95_ms` is the upper bound of the bucket containing the nearest-rank
95th observation (`rank = max(1, ceil(0.95 * n))`); this method name and bucket scheme
are part of the report. Averages remain exact integer-duration sums/counts. The
histogram is bounded independently of request/window count and is maintained for M15
provider calls, M1 provider calls, M15 persistence batches, and M1 persistence batches.

`total_elapsed_ms` starts immediately before the first planning phase and ends at the
terminal transition, summing active work segments across an explicit resume; it
includes planning, provider calls, canonical persistence, validation, snapshot
membership, fingerprinting, and finalization, and excludes time spent queued in
`PENDING`. A benchmark harness additionally records wall-clock scenario elapsed when
process restart downtime must be shown. RSS baseline is sampled immediately before
planning, peak is the process high-water mark sampled throughout the run, and both are
normalized to bytes on the host OS. Peak must be at least baseline; sampling cannot
retain observations or telemetry history.

### 11.4 Closure versus provider-range examples

**Valid:** The missing expected M1 observations before and after a weekend fit inside
one configured M1 provider bound. The planner issues one half-open calendar request
covering the intervening closure. Closure minutes are excluded by validation, and the
request contributes one `total_units`/provider call, not one call per open-session
minute.

**Invalid:** Splitting at every weekend/holiday, counting closed minutes as missing
provider work, or reporting a closure as a provider failure. This changes neither
provider truth nor expected observation semantics and violates the range contract.

**Boundary:** A request exactly `[10:00, 10:10)` is one unit and excludes `10:10`.
Adjacent successful `[10:00, 10:10)` and `[10:10, 10:20)` coverage merges to one
union. A range larger than the configured product bound is split only at deterministic
boundaries (not at closures); a touching boundary belongs to the next half-open
chunk.

### 11.5 Progress, timing, and reuse examples

**Valid progress:** Before any provider I/O, M15 has `completed_units=0`,
`total_units=8`, and M1 has `completed_units=0`, `total_units=40`. After three
successful M15 windows and one successful empty M1 window, the values are `3/8` and
`1/40`; the M1 empty response is acquired coverage and is not fetched again. The
payload remains bounded after 10,000 windows because it retains counters and only the
latest window.

**Invalid progress:** `completed_units=770723` because that is the number of rows,
one scalar `completed_units=43` copied to both products, `total_units=null`, or a
`fetched_ranges` array containing all windows. Each is opaque, misleading, or
request-sized and is rejected by the contract.

**Boundary progress:** A fully covered repeat reports M15 `0/0` and M1 `0/0`, with
`provider.calls=0`; it is `covered`, not complete acquisition work. A failed or
unknown tenth window leaves successful completed count at nine and contributes no
coverage. A later explicit resume recomputes the remainder and writes new totals
before its first call.

**Valid stopped-run reuse:** After process `2dd2dd72-1d97-4b73-af17-f20f91820945`
was stopped, inspection confirms the disposable database is `atlas_test.public`, the
request contract/ranges and StrategyVersion are unchanged, no process owns the
request, every reused M15/M1 window has a durable successful outcome, and canonical
rows are valid, complete, provenance-keyed, and conflict-free. Atlas may explicitly
resume that same request, recompute both products' successful-window unions, issue
only uncovered/confirmed retryable ranges, and then create/link the immutable snapshot.
If both unions cover the required ranges, it must make zero provider calls and proceed
to validation/snapshot construction. This stopped run remains excluded from final
acceptance benchmark evidence; it is reusable durable input only after these checks.

**Invalid stopped-run reuse:** Resetting `atlas_test`, creating a new active request,
trusting stale progress JSON, treating a window with unknown provider outcome as
successful, or using M1 rows to substitute a missing native M15 bar. Any such fact
blocks reuse until explicitly classified; no destructive cleanup is allowed before
the durable-fact audit and resume decision.

### 11.6 Required tests and benchmark gate

Before another genuine full-year benchmark, implementation must add deterministic
tests for:

- exact progress schema and product semantics: totals persisted before the first
  provider call; M15/M1 `0/0`, successful empty/sparse, failure/unknown, retry, resume,
  and warm-up plan-generation cases; no row/minute/scalar/null confusion;
- boundedness and redaction: fixed 8 KiB cap, no request-sized arrays or provider
  secrets/bodies/raw exceptions, O(1) callback work, no whole-range coverage scan per
  callback, and bounded histogram state after a large window count;
- timing correctness: fake-clock M15/M1 provider durations, persistence batch
  durations, exact averages, fixed-histogram nearest-rank p95, validation/snapshot/
  fingerprint/total phase inclusion, zero-denominator null rates, rows/sec numerator,
  and baseline/peak RSS byte normalization;
- closure/range behavior: closure-containing bounded requests are not split by session
  policy, expected closure classification remains validation-only, provider max and
  half-open boundaries are deterministic, and touching/overlapping union reuse makes
  no repeat calls;
- stopped-run recovery: a fixture matching the durable `atlas_test` facts resumes
  from successful acquisition union plus canonical rows, does not trust stale progress,
  never creates a second active request, never reissues successful windows, blocks on
  unknown/conflicting facts, and produces the same snapshot membership/fingerprint as
  a fresh run;
- benchmark evidence: a short representative sample runs first and reports every
  section 11 metric. Exactly one remediation may follow from its measured dominant
  bottleneck; only after that evidence may fresh one-month, genuine one-year,
  covered-repeat one-year, and interrupted/resumed one-year acceptance runs begin.

The full-year gate fails or reports `BLOCKED` when any required metric is absent, when
the covered repeat performs provider I/O, when telemetry grows with window/row count,
when the stopped-run facts are discarded before audit, or when closure splitting is
used to make the numbers look smaller. Fixture timings cannot substitute for
credentialed OANDA evidence; unavailable credentials are reported as `BLOCKED`.
