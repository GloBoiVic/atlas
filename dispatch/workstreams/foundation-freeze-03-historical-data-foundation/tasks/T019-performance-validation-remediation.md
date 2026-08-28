# T019 — Performance validation remediation

Status: `DONE_WITH_CONCERNS`

Fix only the concrete T018 validation regressions:

- eliminate post-insert updates to append-only `dataset_snapshots`; construct the
  immutable row once while retaining atomic snapshot semantics;
- preserve deterministic ordered execution streams at the snapshot boundary;
- remove remaining request-sized collections from V2 coverage/planning paths identified
  by validation, using bounded ordered reads/frontiers.

Add focused regressions, keep sparse/native/immutability semantics unchanged, and run
the full backend suite. Do not start another multi-hour OANDA run until these checks
pass; benchmark evidence remains a later validation gate.

## Receipt

ROLE: BUILD  
STATUS: DONE_WITH_CONCERNS  
BRANCH: `solo/foundation-freeze-03-historical-data-foundation`

### Implementation

- V2 snapshot identity is computed before inserting the parent row; finalization
  performs no `dataset_snapshots` UPDATE. Membership inserts remain bounded and
  inside the caller-owned atomic transaction.
- Execution streams preserve ordered per-component frontiers and reject duplicate
  or reversed observations; database streams use deterministic component order.
- Coverage/planning reads use streamed rows/frontiers: `missing_ranges` no longer
  builds a request-sized minute map and `acquired_windows` no longer calls `.all()`.

### Checks / evidence

- Root `.env` was loaded without printing values; no OANDA or multi-hour run started.
- Focused integration/contract checks: **17 passed**; golden/snapshot checks: **7 passed**.
- Fixture recovery benchmark regression: **1 passed**.
- Ruff: **PASS**; `git diff --check`: **PASS**.
- Full backend suite with root `.env`: **358 passed, 1 skipped, 4 warnings** (~146s).

### Concerns / blockers

- Genuine Intel Mac PostgreSQL/OANDA benchmark evidence remains a later VALIDATE gate.
- Legacy `current_bars` and compatibility benchmark paths retain tuple behavior;
  authoritative V2 paths use streamed seams.
