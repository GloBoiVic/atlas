# Foundation Freeze 03 — Historical Data Foundation

Status: `VALIDATION BLOCKED BY OANDA ACCOUNT CONFIGURATION`
Classification: `Critical`
Workstream: `foundation-freeze-03-historical-data-foundation`
Branch: `solo/foundation-freeze-03-historical-data-foundation`
Base SHA: `38b869bb4341b2f0e5b7f150233428cf69f321cc`

## Outcome

Establish one authoritative V2 historical-data path from strategy and execution
requirements through independently planned provider coverage, durable canonical
observations, validation, immutable deterministic DatasetSnapshots, and Experiment
consumption. Support a one-year EUR/USD request without making duration a user-facing
or architectural ceiling, while preserving bounded OANDA request windows internally.

## Scope

- Audit and correct OANDA acquisition, provider-window pagination, coverage planning,
  persistence, M1 and native M15 reuse, snapshot membership, fingerprinting, and
  failure/resume behavior.
- Persist provider-native observations keyed by provider, instrument, resolution, and
  price component: OANDA EUR/USD M15 MID for analysis and M1 BID/ASK for execution.
- Plan analytical and execution products/ranges independently, including strategy
  warm-up before `trading_start`, and fetch only missing local coverage.
- Persist validated bounded-window progress before continuing; resume from remaining
  local coverage after interruption/failure.
- Remove or quarantine conflicting authoritative paths (legacy M1→M15 derivation,
  obsolete `load_missing`, V1 snapshot behavior, stale 90-day/provider assumptions)
  only where required for this path.
- Add deterministic tests and benchmark evidence for fresh one-month, fresh one-year,
  repeat covered one-year, and recovery scenarios.

## Non-goals

No broader Freeze 04 cleanup, additional providers/instruments, Redis/queues or other
distributed infrastructure, speculative storage redesign, or unrelated UI/product work.

## Acceptance

The user-provided Freeze 03 acceptance list is authoritative. In particular: native
M15 is reusable and never derived in the authoritative Experiment path; M1 BID/ASK is
reusable; product coverage is independent; covered requests make no OANDA calls;
large loads are restart/resume safe; snapshots are immutable and deterministic; no
forward-fill/fabrication; and benchmark timings/request counts are reported.

## Exploration findings

- `MarketDataService` currently exposes `plan_missing`, `load_missing`, and
  `create_snapshot`; the visible implementation plans one `REQUIRED_COMPONENTS` set
  and creates a M1 snapshot path, while `create_snapshot_v2` is present but needs a
  full authority audit.
- `HistoricalDataLoadCoordinator` is the API lifecycle entry point and current feature
  context describes a bounded in-process load with interrupted requests failed rather
  than resumed; this conflicts with Freeze 03 recovery requirements and must be
  resolved explicitly in architecture.
- Current context says base M1 with derived 15m, which conflicts with the requested
  canonical native M15 analytical product. Architecture must supersede this stale
  assumption for the Freeze 03 path and preserve no-fabrication semantics.
- Repository state is `main` with unrelated untracked `.codegraph/` and
  `frontend/.env.local`; these must be cleaned or explicitly resolved before GIT START.

## Architecture status

`ARCHITECTURE.md` is frozen by ARCHITECT. It establishes V2 as the sole new-Experiment
authority, native M15 MID plus native M1 BID/ASK products, independent half-open
coverage, bounded provider windows, per-window durable commits/progress, explicit
resume, immutable membership/fingerprints, and stale-path quarantine. Its required
tests and benchmark evidence are binding.

## Task state

Latest validation found request-sized V2 coverage/metadata collections and fixture
repeat-equivalence telemetry gaps despite a green backend suite. T020 is opened to
resolve those boundedness/equivalence findings before genuine benchmarking.

T018 fixed the generator-factory iterator defect. Fresh validation is required to
verify the remaining immutability-trigger suite failures, bounded behavior, and the
Intel Mac benchmark gates; OANDA account configuration remains an environment gate.

T014 architecture remediation is approved. T017 implemented sparse validation,
strict native M15 semantics, canonical warm-up, and overlapping-window reuse.

The API-path validation correctly planned the completed-bar warm-up and is making
durable progress on `atlas_test`; successive sessions have persisted native M15 and
M1 units but have not reached snapshot creation. Resume/full-year completion, coverage
validation, and repeat evidence remain required. An accidental unusable process
against local `atlas` was disclosed and is excluded from evidence.

T001–T016 are complete with concerns. External review requires a narrow correction to
sparse M1 validity, strict M15 semantics, warm-up authority, and overlapping
acquisition-window reuse. ARCHITECTURE.md must be updated and approved before
implementation. Developer opened a final performance remediation: bound progress,
PostgreSQL reads, fingerprinting, membership insertion, and covered-repeat planning
with Intel Mac RSS/timing evidence. Developer approved the performance architecture;
T018's first slice removed per-window whole-range scans and bounded progress, but left
request-sized snapshot ORM collections and lacks real Intel Mac benchmark evidence.
T018 continuation finished bounded reads/chunked membership and deterministic
regressions but still requires profile-guided market_bars persistence review and
genuine benchmark evidence. The stopped full-year load is pre-remediation evidence and
must not be resumed unchanged; validation waits until optimization is complete. T019
is opened for the append-only snapshot update, ordered execution stream, and remaining
request-sized collection defects found by validation. T019 fixed these defects and the
full backend suite is green; fresh validation still finds authoritative V2
`current_bars` tuple materialization and tuple-accumulated planning plus an
inconsistent compatibility fallback. T020 is reopened for this narrow source-audit
remediation before any further long live run.

T001–T012 are complete with concerns. T008 repaired the stale API fixture but its
full-calendar-year durable run exposed a live schema constraint still enforcing
one-minute intervals on native M15 rows. T009 reconciled the migration names, but
validation requires a clean disposable database run. T009's naming fix still double-
prefixed the generated constraint on a fresh schema; T010 corrected migration naming,
but the real full-year load failed during persistence after durable progress. T011 is
opened to diagnose that product/shape failure and complete live evidence; T011 bounded
membership inserts and persisted the full native products, but the first run timed out
before snapshot creation. The configured validation run found no T011 coverage in the
durable database and could not migrate the legacy database because of immutable rows.
Developer has now explicitly authorized resetting the current disposable database;
fresh validation reset it and migrations reached head. T012 added effective-dated
provider holiday closures without fabrication, but its rerun reached head and
persisted partial M15 coverage before the execution window ended. Resume from durable
progress and complete full-year/repeat evidence without weakening coverage. T012
classified holiday closures but left 1,293 scattered expected-session gaps; T013 is
opened to diagnose acquisition boundaries/provider sparsity and finish or precisely
block the live evidence. Developer clarified that successful provider-window acquisition
is distinct from sparse observation continuity: sparse M1 BID/ASK windows must be
reusable without fabricating minutes, while native M15 analytical completeness remains
strict. T014 architecture remediation must classify the 1,293 gaps by product, closure,
constituent, and window outcome before implementation. ARCHITECTURE.md now freezes the
sparse-acquisition correction; T014 implemented acquisition coverage versus
observation continuity, but full-year snapshot materialization timed out. T015 is
opened to bound snapshot membership/fingerprint operations without changing semantics,
then complete live evidence. T015 bounded snapshot membership batches and added
performance coverage but could not run live evidence in its worker environment. T015 is
complete with concerns; fresh validation must use root `.env` and the authorized
disposable database.
local PostgreSQL database/schema; discard stale local Experiment/result data, preserve
immutable-facts protections, migrate from a clean state through head, and rerun the
genuine full-calendar-year OANDA load plus covered repeat evidence. PostgreSQL and real
OANDA are available and must be validated without exposing secrets.

## BUILD tasks

- `T001-storage-contract-and-coverage`: extend canonical persistence and independent
  product coverage/missing-range planning, including completed-bar-count analytical
  warm-up, native-resolution provenance, idempotency, conflict handling, and bounded
  bulk operations.
- `T002-oanda-native-acquisition`: implement native M15 MID and M1 BID/ASK provider
  requests, granularity-appropriate bounded windows, normalization, completed filtering,
  and redacted failure behavior.
- `T003-durable-load-resume`: replace incompatible no-resume lifecycle behavior with
  durable per-window progress, bounded batches over arbitrarily large missing plans,
  atomic observation commits, explicit safe resume, and remaining-coverage retry
  semantics. Never impose a request-window-count research limit.
- `T004-v2-snapshot-experiment-path`: make immutable deterministic V2 snapshot
  membership/fingerprinting and Experiment validation consume native independent
  products; quarantine stale snapshot/load authorities.
- `T005-regressions-benchmarks-cleanup`: add end-to-end deterministic tests and required
  fixture plus credentialed-real (when available) one-month/one-year/repeat/recovery
  benchmark evidence, then remove only unreachable stale historical-data authority
  required by V2.
- `T006-review-remediation`: remove residual warm-up ceilings, stale V2 preparation
  planning, and inaccurate public product metadata; add regressions.
- `T007-live-validation-remediation`: fix V2 `Bar` ordering, reconcile the
  environment-sensitive configuration test, and prove real repeat reuse.
- `T008-live-evidence-completion`: repair the stale API fixture and prove durable
  full-calendar-year OANDA repeat reuse with zero provider calls.
- `T009-native-m15-migration-remediation`: reconcile native M15 migration constraint
  names and rerun full-year durable load/repeat evidence.
- `T010-fix-migration-naming`: correct the fresh-schema constraint naming bug and rerun
  the approved live evidence.
- `T011-full-year-persistence-remediation`: diagnose the real full-year persistence
  failure and complete unchanged full-year/repeat evidence.
- `T012-live-coverage-gap-remediation`: diagnose and correctly classify remaining live
  provider gaps, then complete full-year/repeat evidence without fabrication.
- `T013-oanda-gap-diagnosis`: diagnose scattered expected-session gaps and complete or
  precisely document full-year/repeat evidence.
- `T014-sparse-acquisition-semantics`: implement acquisition-coverage versus
  observation-continuity semantics and required V2 tests, then rerun live evidence.
- `T015-sparse-snapshot-performance`: bound sparse snapshot materialization and complete
  full-year snapshot/repeat evidence without changing semantics.
- `T016-suite-reconciliation`: reconcile stale migration/frontier assertions and safe
  disposable migration teardown, then rerun the full suite.
- `T017-sparse-reuse-and-warmup-remediation`: implement approved sparse execution,
  strict analytical, canonical warm-up, and overlapping-window semantics.
- `T019-performance-validation-remediation`: fix append-only snapshot finalization,
  ordered execution streams, and remaining V2 request-sized collections.
- `T020-final-bounded-v2-path`: eliminate remaining authoritative V2 request-sized
  collections and prove deterministic repeat equivalence/telemetry.

Dependency order: T001 and T002 may proceed independently after approval; T003 depends
on both; T004 depends on T001–T003; T005 follows the implementation and is the final
BUILD task. Each task must finish with a receipt in its task file.

## Next action

Developer approval received and GIT START completed. CodeGraph was queried after each
BUILD slice and reported no stale-index banner; unrelated untracked `.codegraph/`
and `frontend/.env.local` are intentionally untouched. T015 is complete with concerns;
fresh validation proved live snapshot/repeat semantics but found stale suite assertions
and guarded teardown. T016 reconciled those assertions and teardown; fresh validation
now passes the full backend suite and confirms genuine full-year sparse
snapshot/repeat evidence with zero repeat provider calls. External review corrections
are reconciled into ARCHITECTURE.md; T017 is complete with concerns and T018
performance continuation completed bounded V2 streaming, incremental fingerprinting,
Core batch membership writes, and bounded gap generation. Multi-hour validation is now
authorized; T018's iterator remediation is complete with concerns. Fresh validation
must load root `.env`, verify immutability-trigger behavior, profile the actual Intel
Mac/PostgreSQL/OANDA path, and report any unavailable credential gate. T019 is complete
with concerns; T020 validation remediation is complete. Final validation passes the
full backend suite and authoritative bounded-path audit, but the genuine full-year
benchmark is blocked because root `.env` lacks an OANDA account ID. No review/merge
readiness is claimed until that evidence is supplied.
