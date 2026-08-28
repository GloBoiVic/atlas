# Foundation Freeze 03 — Historical Data Foundation

Status: `REVIEW PASS — READY TO COMMIT`
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
remediation before any further long live run. External review confirmed the historical
source is token-only; T021 is correcting the invented account-ID benchmark gate and
will run fresh genuine evidence.

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
- `T021-token-only-live-benchmark`: correct the harness to use token-only historical
  OANDA configuration and collect final genuine performance evidence.
- `T022-live-snapshot-persistence-remediation`: diagnose and fix live V2 snapshot
  persistence, then rerun fresh/repeat/recovery evidence.
- `T023-diagnose-live-snapshot-write`: reproduce and fix the remaining bounded live
  snapshot write failure without another provider load.
- `T024-coordinator-snapshot-linkage`: fix coordinator warm-up completion and link the
  immutable snapshot to the load request.
- `T025-streaming-snapshot-memory`: remove hidden full-year snapshot buffering and prove
  bounded memory/time before live validation.
- `T026-live-finalization-profile`: profile and fix the remaining full-year finalization
  hotspot without timeout increases or semantic weakening.
- `T027-phase-telemetry-and-progress`: implement the frozen phase telemetry,
  per-product provider progress, bounded metrics, range-splitting regressions, and
  short-sample-first benchmark gate.
- `T028-fingerprint-hotspot-remediation`: remediate only the measured fingerprinting
  hotspot, prove byte-identical fingerprints, and rerun the short sample before live
  acceptance.
- `T029-closure-only-resume-ranges`: prevent closure-only durable-union holes from
  becoming needless provider requests while retaining closure-bridging bounded ranges.

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
benchmark was incorrectly blocked by a harness account-ID gate. T021 is correcting the
harness to use the token-only historical source; no account-ID requirement may be added.
T021 completed fresh acquisition but snapshot persistence failed; T022 fixed the
fingerprint/gap parity defect with deterministic regressions. Developer approved fresh
validation using the token-only historical source and disposable PostgreSQL; run final
live/performance evidence now without resuming the stopped load. T023 diagnosed and
fixed the gap-policy constraint mismatch without another OANDA request. Fresh
validation must materialize the existing full-year snapshot and repeat from durable
bars, then run final performance/full-suite checks. T024 fixed coordinator
warm-up/session handling and snapshot linkage with focused regressions. Fresh validation
must now run the genuine token-only full-year lifecycle, repeat, recovery, and final
performance suite. Validation measured approximately 1.15 GiB RSS and incomplete
snapshot finalization; T025 removed ORM/result buffering in the V2 snapshot stream and
added bounded local memory regression evidence. Fresh genuine validation still exceeded
two 20-minute windows during finalization; T026 added set-based snapshot INSERT
validation and finalization telemetry with focused profile evidence. Fresh validation
may now run the genuine benchmark; no timeout increase or unchanged pre-remediation
rerun is permitted.

## Developer feedback — current performance run stopped

The full-year process for request `2dd2dd72-1d97-4b73-af17-f20f91820945` was stopped
before acceptance evidence and is explicitly excluded from final performance evidence.
The disposable `atlas_test` database was not reset. Its durable canonical facts remain
inspectable: the request is still `RUNNING` with committed observations and successful
M15/M1 acquisition-window records, while no snapshot is linked to that request. The
Freeze 03 crash/resume contract permits reuse of those facts only after validation
confirms that successful-window union and canonical rows are the resume authority; no
cleanup or destructive reset is allowed before that confirmation.

The stopped run also exposed a telemetry defect. In the current V2 path,
`completed_units` is the process-wide number of successfully fetched-and-persisted
provider windows (`committed_count`), shared across analytical and execution products;
it is not bars, minutes, or rows. The same value is copied into each product's progress
object, and `total_units` is always `None`. This is opaque and must be replaced with
per-product expected/completed provider-request counts, with the expected total written
before the first provider call.

Before any new long run, telemetry must separately report acquisition planning, M15/M1
provider request counts and elapsed OANDA request time, M15/M1 persistence time, final
coverage/integrity validation, snapshot membership construction, fingerprinting, total
elapsed time, and baseline/peak RSS. It must include expected requests before acquisition,
completed/total requests by product, average/p95 OANDA request duration, average/p95
database persistence duration per batch, and rows inserted per second. Session closures
remain validation semantics only; they must not split otherwise safely bounded OANDA
calendar ranges into tiny requests.

No speculative optimization is authorized. Run a short representative sample with the
complete telemetry first, identify the dominant measured bottleneck, make one evidence-
based fix, and only then run genuine full-year acceptance evidence.

T027 completed the telemetry/progress implementation and its short sample found
fingerprinting dominant. T028 made the single authorized field-level fingerprint
remediation; its short sample reduced representative fresh-year fingerprinting from
4,652 ms to 2,987 ms and total elapsed from 10,120 ms to 7,199 ms, with unchanged
fingerprints across fresh/repeat/resumed fixtures. No genuine OANDA run has been started
since the stopped attempt. VALIDATE must now independently audit the implementation,
confirm stopped-run durable-fact reuse/resume safety, and run the genuine acceptance
benchmark only with complete telemetry and progress.

The durable stopped-run audit found 261 inter-window M1 holes containing zero expected
open-session minutes; they are closure-only legacy gaps, not provider work. T029 is the
narrow remediation to prevent those holes from being re-requested on resume. No new
full-year run may start until T029 is complete and its focused tests pass.

## Developer feedback — final validation order

Disk pressure is resolved (approximately 69 GiB free). Do not resume the old stopped
full-year process unchanged, create further speculative remediation tasks, or increase
timeouts. T029 is the final narrow range correction. Validation must proceed in this
order: confirm real per-product `completed_units`/`total_units`; verify all phase
instrumentation; run a short representative load and inspect request counts,
throughput, progress, and RSS; run the genuine fresh full-calendar-year benchmark if
healthy; run a covered repeat proving zero OANDA calls, identical fingerprint and
membership, and materially faster completion; run interrupted/resume equivalence and
the full backend suite. The stopped attempt remains excluded from final performance
evidence, but its durable facts may be reused only under the confirmed Freeze 03
resume contract. The final receipt must include every requested metric and the branch
must be committed and pushed for independent review.

The ordered validation reached the genuine isolated year and completed acquisition
(`m15=9/9`, `m1=132/132`) with telemetry, but snapshot creation failed because 503
returned observations were classified inside session closures. This is the only
authorized remediation continuation: diagnose the exact closure/final-validation
contract failure and fix it without weakening closure semantics or splitting bounded
provider ranges. No additional speculative task or timeout change is permitted; the
validation order restarts at the short representative check after this correction.

T026 continuation fixed the isolated-year failure at the OANDA canonicalization
boundary: complete execution candles in unavailable-session intervals are validated
then omitted from canonical M1 execution data, while native M15 remains untouched and
bounded requests still bridge closures. The short representative benchmark was rerun
after that fix; validation now resumes the prescribed ordered gates with no additional
task or speculative optimization.

The final validator found one non-performance completion defect: the full backend suite
still asserts the obsolete migration head `0018_acquisition_windows`, while the
authoritative schema is at `0020_fix_snapshot_guard`. This is a required test-contract
reconciliation only, not a new optimization or task. The suite must be rerun against
an isolated schema so it cannot destroy the already-audited disposable data; the
stopped-run facts were successfully reused before the suite teardown and remain
excluded from final performance evidence.

The stale-head assertion was reconciled to `0020_fix_snapshot_guard` without runtime
or database changes. Validation must rerun the full backend suite on a fresh isolated
schema, not `atlas_test`, then reconcile the final evidence; no new OANDA run is needed
for this test-only correction.

## Approved narrow remediation pass

The developer approved one narrow remediation pass treating all six independent-review
findings as authoritative Freeze 03 blockers. This pass adds no architecture and no
unrelated refactor or optimization. Preserve the already-proven OANDA chunking, sparse
M1 semantics, native M15 semantics, snapshot determinism, and bounded-memory behavior.
No genuine full-year OANDA run is required unless VALIDATE determines changed behavior
invalidates existing live acceptance evidence.

1. T030: atomically commit canonical observations and successful acquisition-window
   outcome in one short transaction; provider I/O remains outside it; add interruption
   coverage around the commit boundary.
2. T031: reuse successful acquisition-window union for native M15 as well as M1 while
   retaining strict native-M15 validation; add empty/sparse M15 repeat coverage.
3. T032: emit and durably record the frozen `FINALIZING` progress phase.
4. T033: replace request-sized ORM `.all()`/tuple/set materialization in authoritative
   V2 Experiment coverage validation with bounded streaming/set-based reads.
5. T034: check the completion transition result and persist an inspectable fail-closed
   terminal outcome when completion cannot be committed.
6. T035: make terminal snapshot/fingerprint metrics count all hashed records including
   gaps, or explicitly separate counts without presenting an incomplete total.

The review also confirmed the intended uncommitted changes are present and that
untracked `.codegraph/` and `frontend/.env.local` must remain excluded from any commit.

Dependency order: T030 → T031 → T032 → T033 → T034 → T035. Each task requires focused
regression coverage and a complete BUILD receipt before the next task starts. VALIDATE
follows all six BUILD tasks; REVIEW follows a passing VALIDATION.

## Validation procedural incident

The remediation implementation and all six focused findings pass source/test review,
but VALIDATE is `BLOCKED`: its first migration invocation used a malformed derived URL
that resolved to `atlas_test`, and an established migration fixture executed
`DROP SCHEMA public CASCADE` before the URL failure. All subsequent checks used the
fresh isolated database/schema, and the prior receipt already recorded that `atlas_test`
was not independently inspectable after an earlier suite teardown. Nevertheless, this
violated the explicit no-reset/delete constraint during the current pass. The developer
accepted this as a documented validation-process incident; it is not an implementation
blocker, must not create a remediation task, and must not trigger a repeat of the genuine
full-year benchmark or already-passed validation.

## Remediation task state

- T030 `DONE_WITH_CONCERNS`
- T031 `DONE`
- T032 `DONE`
- T033 `DONE_WITH_CONCERNS`
- T034 `DONE`
- T035 `DONE_WITH_CONCERNS`

## Approved final narrow remediation pass

The developer approved remediation of the two remaining IMPORTANT findings only. This
pass does not reopen T030–T035, add architecture, or introduce unrelated refactoring,
performance work, cleanup, or context changes. Existing live-year/repeat/recovery
evidence remains accepted unless VALIDATE determines these boundary changes materially
invalidate it. No genuine full-year OANDA benchmark will be rerun.

1. T036 closes all V2 planning-read transactions before provider work is yielded or
   fetched, preserving planning semantics and progress totals.
2. T037 removes request-sized missing-range list/tuple accumulation from authoritative
   V2 planning, retaining only bounded frontier/state and diagnostics while preserving
   closure handling, acquisition-union subtraction, strict M15 semantics, and provider
   chunk bounds.

Dependency order: T036 → T037. VALIDATE follows both tasks, then fresh REVIEW follows
validation. The accepted validation-process incident, existing live evidence, and
excluded `.codegraph/`/`frontend/.env.local` are not reopened.

## Final remediation task state

- T036 `DONE`
- T037 `DONE`

## Final review

Fresh independent REVIEW passed after T036/T037. No Critical or Important Freeze 03
violations remain. The accepted validation-process incident, existing live-year/repeat/
recovery evidence, and no-new-benchmark exception remain documented. Commit only the
intended `backend/` and `dispatch/` changes; exclude `.codegraph/` and
`frontend/.env.local`.
