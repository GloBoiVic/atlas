# Validation

Status: `FAIL` — genuine OANDA full-year evidence `BLOCKED`
Role: `VALIDATE`
Workstream: `foundation-freeze-03-historical-data-foundation`
Branch: `solo/foundation-freeze-03-historical-data-foundation`

Fresh validation ran 2026-08-27 from `/Users/vike/Desktop/atlas` after T020.
CWD, repository root, branch, and CodeGraph were verified. Root `.env` was loaded
without exposing values. Only this artifact was changed; implementation, branch,
and Git history were not changed. No stopped pre-remediation load was resumed.

## Environment gate

- `ATLAS_DATABASE_URL`, `ATLAS_TEST_DATABASE_URL`, and
  `ATLAS_OANDA_API_TOKEN`: configured (presence-only check).
- `ATLAS_OANDA_ACCOUNT_ID`, `OANDA_ACCOUNT_ID`, and
  `ATLAS_EXTERNAL_OANDA_ACCOUNT_ID`: absent.
- Therefore no live OANDA run was started. Genuine fresh one-month, fresh
  calendar-year, covered-repeat calendar-year, and interrupted/resumed
  calendar-year evidence is blocked by the missing safe account target. No
  database reset or long run was performed.

## Checks

- Full backend suite with root `.env`: **359 passed, 1 skipped, 4 warnings** in
  **208.98s**.
- Focused V2/ingestion/repository/migration/load suite: **48 passed** in
  **89.76s**.
- Warnings: one Starlette/httpx deprecation and three unknown
  `price_analysis` marks.
- Ruff was not an acceptance gate; it reports existing repository-wide style
  findings, including unrelated tests.

## Deterministic fixture benchmark

`uv run python -m backend.market_data.freeze03_benchmark` completed through the
real V2 planner, acquisition seam, persistence seam, snapshot path, and
incremental fingerprint path. Fingerprints are real SHA-256 values. Times are
seconds; provider calls are `M15/M1`; RSS is process `ru_maxrss`.

| Scenario | calls | inserted/reused | repeat calls | planning/coverage | persistence | snapshot/fingerprint | total | max batch/progress | peak RSS | fingerprint |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| fresh month | 24/24 | 70,975/0 | 0 | 0.403001/0.088907 | 1.308493 | 0.000004/11.525815 | 19.044363 | 2,868 / 415 B | 130,527,232 B | `4c81385bdf1413da55857b78148b115169b35e30889148ae0159d7e89af5cfb6` |
| fresh representative year | 24/24 | 68,126/0 | 0 | 0.458907/0.104120 | 1.214234 | 0.000003/7.781196 | 13.613552 | 2,868 / 415 B | 130,527,232 B | `037e9a6fb4a97143dd13a99720904cda9864faaf04039b35714b2a8af647ed01` |
| covered repeat representative year | 0/0 | 68,126/68,126 | 0 | 1.142049/0.292894 | 1.455824 | 0.000003/7.203717 | 9.822558 | 2,868 / 0 B | 130,867,200 B | `037e9a6fb4a97143dd13a99720904cda9864faaf04039b35714b2a8af647ed01` |
| interrupted/resumed representative year | 35/24 | 68,126/933 | 48 | 0.688884/0.090140 | 1.109625 | 0.000001/7.817414 | 13.846155 | 2,868 / 417 B | 130,867,200 B | `037e9a6fb4a97143dd13a99720904cda9864faaf04039b35714b2a8af647ed01` |

The representative-year fresh, repeat, and resumed fingerprints match; the
covered repeat made zero provider calls. This fixture's “year” is the existing
representative month and is not full-calendar-year, PostgreSQL, or credentialed
OANDA evidence.

## Authoritative V2 source/AST audit

`backend/market_data/ingestion.py`, `fingerprint.py`,
`freeze03_benchmark.py`, `market_data_repository.py`, and
`historical_data_load_repository.py` were audited with AST and CodeGraph.

- **PASS:** V2 coverage uses ordered `current_bars_stream`; snapshot execution
  requires `current_bar_rows_stream` and does not use a compatibility fallback.
- **PASS:** authoritative V2 planning, coverage, snapshot, membership,
  fingerprint, and progress paths contain no request-sized `tuple`, `list`,
  `set`, `.all()`, or full-iterable `sorted()` materialization. Batches are
  bounded; progress is O(1); fingerprinting is incremental and ordered.
- **PASS:** native M15/MID strictness, sparse M1 BID/ASK semantics, overlap and
  subrange acquisition reuse, immutable snapshots, and deterministic repeat
  fingerprints are covered by the focused suite and fixture telemetry.
- **PASS:** legacy materialization remains only in explicitly non-authoritative
  APIs (`create_snapshot` and `load_v2_incremental`); V2 does not route through
  them.

## Verdict

Implementation/source and deterministic fixture checks pass. Overall acceptance
is **FAIL/BLOCKED** because the required genuine full-calendar-year OANDA
Practice benchmark cannot safely run without an account ID. Configure the
disposable OANDA Practice account target, then run fresh-process month/year,
repeat, and interruption benchmarks without resuming the stopped old load.

ROLE: VALIDATE
STATUS: FAIL / genuine OANDA evidence BLOCKED
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md`
FILES CHANGED: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/VALIDATION.md`
CHECKS / EVIDENCE: Full suite 359/1 skipped; focused suite 48 passed; AST/CodeGraph audit passed; deterministic real-fingerprint fixture benchmark passed with zero-call repeat and bounded telemetry.
FINDINGS / CONCERNS: OANDA account ID absent; genuine full-calendar-year PostgreSQL/OANDA evidence was not started and remains the sole acceptance blocker.
