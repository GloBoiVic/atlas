# T018 — V2 performance remediation

Status: `IN_PROGRESS` (validation remediation)

Implement the approved performance contract only: incremental O(1) progress updates,
bounded PostgreSQL reads, streamed/chunked deterministic fingerprinting, bounded
immutable membership insertion without whole-range Python materialization, and
acquisition-coverage-first repeat planning. Preserve sparse/native semantics,
determinism, immutability, and crash/resume safety. Benchmark this Intel Mac with a
genuine full-calendar-year dataset, reporting OANDA, persistence, planning/coverage,
snapshot/fingerprint, total time, peak RSS, fresh calls, and covered-repeat time/calls.
Full backend suite must remain green.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
BRANCH: `solo/foundation-freeze-03-historical-data-foundation`  
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T018-performance-remediation.md`

### Implementation

- `load_v2` progress is now bounded O(1): no retained fetched/committed window
  history and no whole-range `_coverage` call after each provider window. The
  callback carries only the current window, cumulative counters, and bounded
  counts; durable resume remains canonical bars plus acquisition-window union.
- `HistoricalDataLoadRepository.record_progress` writes empty compatibility
  range arrays and bounded counters/latest-window progress instead of copying
  request-sized arrays into JSON.
- M1 repeat planning now reads acquisition coverage first and scans current
  observations only for uncovered remainders. Successful sparse/empty coverage
  therefore avoids the full-calendar observation scan and provider calls.
- Canonical V2 fingerprint metadata now includes the clipped merged execution
  acquisition union rather than raw request-window identities.
- Expected-range coalescing no longer materializes a set of every minute.

### Checks / evidence

- CodeGraph queried first; repository root/CWD/branch verified. No secrets or
  provider response bodies were recorded.
- `ruff check backend/market_data/ingestion.py backend/market_data/historical_load.py backend/persistence/historical_data_load_repository.py` — PASS.
- Focused deterministic regressions: **6 passed** (benchmark test excluded).
- Backend suite attempt: **314 passed, 30 skipped, 13 errors**. Errors are
  integration setup failures because `ATLAS_TEST_DATABASE_URL` was not present;
  the full backend suite is therefore not green/evidenced.
- Non-integration backend suite: **313 passed, 7 skipped** (one warning).

### Concerns / incomplete evidence

- The approved contract's remaining bounded-read and snapshot requirements are
  not fully implemented in this slice: `current_bars`/snapshot construction
  still contain request-sized ORM materialization, and V2 membership insertion
  still builds complete row lists before batched executemany.
- No genuine Intel Mac 8 GB full-calendar-year fresh/repeat/interrupted-resumed
  benchmark was run in this worker. OANDA calls/time, persistence/planning/
  coverage/snapshot/fingerprint/total timing, baseline/peak RSS, batch and
  progress-payload maxima, inserted/reused counts, and exact snapshot/fingerprint
are consequently **unavailable**, not substituted with fixture claims.

## Continuation required

Replace remaining request-sized ORM/materialized collections in snapshot reads,
fingerprinting, and immutable membership insertion with bounded ordered streaming or
set-based batch operations. Then run configured PostgreSQL/OANDA Intel Mac benchmarks
and the full suite; do not claim completion from fixture-only evidence.

## Continuation evidence (2026-08-27)

- Snapshot descriptor, current-bar, and immutable V2 membership reads now use
  SQLAlchemy `yield_per(10_000)` rather than ORM `.all()` result-list loading.
- Added `current_bars_stream()` as the bounded ordered read seam for callers that can
  consume an iterable. V2 analytical, execution, and gap membership inserts now feed
  bounded 10,000-row Core executemany batches without constructing a complete insert
  payload; legacy membership insertion is likewise chunked. The enclosing transaction
  remains atomic.
- Added a regression proving V2 fingerprints are unchanged when analytical and
  execution producers use batch sizes 1, 3, 7, 37, 113, or 10,000.
- Focused checks: **22 passed, 5 skipped** across snapshot/fingerprint, market-data,
  and repository tests. `git diff --check` passed.
- Full backend attempt: **315 passed, 30 skipped, 13 errors**. All errors are
  integration setup failures because `ATLAS_TEST_DATABASE_URL` is unset.

### Remaining blockers / concerns

- The V2 service boundary still accepts `Sequence` analytical/execution inputs and
  performs validation/counting before persistence; a genuine full-calendar-year
  end-to-end proof of constant Python RSS therefore remains unavailable.
- No disposable PostgreSQL/OANDA benchmark was run: configured test DB URL is absent
  and no provider benchmark credentials were used. Baseline/peak RSS, provider and
  persistence timings, planning/coverage/snapshot/fingerprint totals, calls,
inserted/reused counts, progress-payload maxima, and interrupted/resumed results are
  **not evidenced** and are not substituted with fixture claims.

## Continuation receipt (2026-08-27, BUILD)

- V2 snapshot creation now consumes ordered analytical and execution iterables;
  production execution rows use `yield_per(10_000)` with provenance IDs, and the
  load path no longer materializes the full native-M15 range before snapshotting.
- Added `V2FingerprintBuilder`, which hashes header and membership sections
  incrementally while Core membership inserts remain bounded at 10,000 rows.
  Validation is still complete: native/type/range/order checks, current-row and
  venue checks, fingerprint verification, and one enclosing atomic transaction.
- Gap membership generation is streamed from persisted analytical membership when
  the caller does not provide explicit gaps; no expected-M15 set is built.
- Focused checks: `14 passed`; `ruff check` and `git diff --check` pass after the
  final formatting check. No multi-hour live validation was run.

### Remaining benchmark plan

- Configure a disposable PostgreSQL URL and representative/full-year fixture;
  profile `market_bars` ORM construction versus Core/executemany separately,
  then record provider/persistence/planning/coverage/snapshot/fingerprint/total
  timings, peak RSS, batch maxima, fresh/repeat calls, and interrupted/resumed
  equivalence. Repeat with real OANDA only after credentials are explicitly
  configured; do not resume the stopped pre-remediation run unchanged.

## Current continuation scope

The stopped full-year run is pre-remediation evidence and must not be resumed unchanged.
Finish streaming the remaining request-sized V2 inputs/reads and profile the
`market_bars` persistence path. Only replace ORM object creation with bounded
SQLAlchemy Core/executemany if profiling proves it materially dominant, preserving all
validation, idempotency, conflict, and immutability rules. Then collect the required
genuine Intel Mac benchmarks before validation.

## Validation remediation

Fix the snapshot membership generator-factory regression reported by VALIDATE: pass
iterators, not generator factory callables, to bounded insertion. Add regression
coverage and rerun deterministic/full suites. Do not weaken streaming or immutability.

## Continuation receipt (2026-08-27, BUILD — T018 validation remediation)

- Fixed `DatasetSnapshotRepository.create_v2_validated` to pass the produced
  iterators (`analytical_rows()`, `execution_rows()`, and `gap_rows()`) to bounded
  insertion instead of generator factory callables. Validation, ordering,
  fingerprint, transaction, and immutability behavior are unchanged.
- Regression coverage exercises all three membership streams as iterators in
  `test_v2_bulk_memberships_persist_representative_large_batch`, including the
  >10,000-row bounded analytical insertion shape and persisted counts.
- With root `.env` loaded, focused persistence check: **1 passed**. Snapshot
  contract plus repository module: **12 passed**.
- `ruff check backend/persistence/market_data_repository.py
  backend/tests/integration/test_market_data_repositories.py` — **PASS**;
  `git diff --check` — **PASS**.
- With root `.env` loaded, `pytest -q backend/tests` — **343 passed, 1 skipped,
  15 failed, 4 warnings (187.30s)**. Failures are snapshot-creation paths
  attempting the post-insert `dataset_snapshots` fingerprint/integrity update,
  rejected by the database immutability trigger; this narrow remediation did not
  broaden into that separate persistence design issue.
- No OANDA calls, multi-hour validation, credentials, or secrets were used or
  recorded.

### Remaining benchmark gates

- Run the genuine Intel Mac full-year benchmark with disposable PostgreSQL and a
  representative/full-year fixture: fresh, repeat, interrupted/resumed,
  provider/persistence/planning/coverage/snapshot/fingerprint/total timings, peak
  RSS, bounded batch/progress maxima, fresh and covered-repeat calls,
  inserted/reused counts, and exact snapshot/fingerprint equivalence.
- Resolve or explicitly disposition the immutable-snapshot finalization failures
  before claiming the full backend suite green. Do not resume the stopped
  pre-remediation run unchanged or run multi-hour OANDA validation in this task.
