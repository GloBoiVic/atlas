# Foundation Freeze 03 — Historical Data Foundation

Status: `READY FOR MERGE APPROVAL`
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

T001–T006 are complete with concerns. Review remediation removed the residual warm-up
ceilings, quarantined shared planning from V2 preparation, and corrected public product
metadata. Fresh validation and review passed with no unresolved IMPORTANT/CRITICAL
findings. PostgreSQL-backed and credentialed OANDA evidence remain explicitly blocked
by environment and are preserved as open gates in the final report.

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

Dependency order: T001 and T002 may proceed independently after approval; T003 depends
on both; T004 depends on T001–T003; T005 follows the implementation and is the final
BUILD task. Each task must finish with a receipt in its task file.

## Next action

Developer approval received and GIT START completed. CodeGraph was queried after each
BUILD slice and reported no stale-index banner; unrelated untracked `.codegraph/`
and `frontend/.env.local` are intentionally untouched. Tasks, validation, review,
branch, status, and diff checks are complete. Await explicit merge approval.
