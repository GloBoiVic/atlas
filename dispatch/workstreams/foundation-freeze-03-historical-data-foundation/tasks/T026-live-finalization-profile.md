# T026 — Live finalization profile

Status: `DONE_WITH_CONCERNS`

## Receipt

The dominant hotspot was the row-level PostgreSQL V2 append-only trigger: every execution
membership row performed a snapshot existence lookup and a market-bar validation lookup.
The existing 10,000-row Core executemany batches therefore still incurred approximately
one million trigger-side lookups for the 743,204-row live execution product. Ordered reads,
incremental fingerprinting, generated gaps, coordinator linkage, and transaction lifetime
were not the limiting operation in the source audit.

Migrations `0019_snapshot_insert_guard` and `0020_fix_snapshot_guard` correct this without
weakening semantics: INSERT validation uses a transition table once per bounded statement,
while separate row-level UPDATE/DELETE guards retain append-only immutability. The execution
validity predicate is unchanged. Repository telemetry records analytical/execution/gap row
counts, bounded batch counts, and per-stage Core insert seconds in
`last_v2_finalization_telemetry`.

A PostgreSQL fixture profile covering 1,201 analytical rows plus 100 gaps completed in 3.93s
(the same fixture before the trigger correction completed in 4.38s); the regression asserted
one bounded analytical batch and non-negative insert telemetry. `alembic check` passed and
focused PostgreSQL regressions passed (2 tests). The deterministic benchmark harness was
attempted but exceeded its 120s command bound without emitting a result; no timeout was
increased.

Benchmark readiness: **READY FOR A FRESH GENUINE FULL-YEAR RUN**, subject to validation
capturing required live timing/RSS/batch/progress/repeat/recovery evidence. This BUILD task
did not start another OANDA acquisition and does not claim live completion.

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T026-live-finalization-profile.md`
FILES CHANGED: `backend/persistence/market_data_repository.py`, `backend/persistence/migrations/versions/0019_set_based_snapshot_insert_guard.py`, `backend/persistence/migrations/versions/0020_fix_snapshot_insert_guard.py`, `backend/tests/integration/test_market_data_repositories.py`
CHECKS / EVIDENCE: CodeGraph-first source audit; PostgreSQL focused regressions 2 passed in 3.93s; `alembic check` passed; Ruff passed after formatting; no OANDA acquisition.
FINDINGS / CONCERNS: Full-year live rerun and emitted deterministic benchmark output remain validation work; the available fixture profile was smaller than the 743,204-row live execution membership.

## Continuation — fresh-year validation failure

The ordered validator ran the post-remediation genuine year in an isolated schema. All
9 M15 and 132 M1 provider chunks completed, but final V2 validation rejected the
snapshot (`SNAPSHOT_CREATION_FAILED`) after finding 503 provider observations classified
inside session closures. Diagnose and fix this exact finalization/validation failure
without weakening native M15, sparse M1, closure, provenance, or immutability semantics,
and without splitting bounded provider requests at session closures. No new long run
may start until the fix has focused regression evidence.

## Continuation receipt

The failure was at the OANDA canonicalization boundary: `fetch_execution_m1` retained
provider-returned M1 candles whose timestamps classified as `UNAVAILABLE_SESSION` under
the frozen policy. The durable M1 rows therefore contained 503 closure observations;
V2's unchanged `validate_coverage(...).execution_valid` correctly reported closure
anomalies and snapshot creation stopped before immutable membership insertion.

The smallest fix is execution-only normalization. After timestamp, range, alignment,
and duplicate validation, the OANDA source still validates every complete candle through
`_group`, but omits M1 candles/incomplete markers classified in the unavailable session
from the canonical execution result. Native M15 normalization is untouched, the legacy
generic M1 path is untouched, no observations are fabricated, and acquisition remains a
single bounded calendar request that may bridge closures. Existing coverage, sparse
one-sided/unknown, provenance, immutable membership, and fingerprint code is unchanged.

Deterministic regression evidence covers both Friday and Sunday closure boundaries in
one request (one provider call; only open-session observations survive) and proves a
closure-time native M15 candle is not filtered. The relevant source, coverage, V2
regression, snapshot fingerprint, and guarded repository tests passed; existing fixture
fingerprint/repeat-equivalence assertions remain green. No OANDA request or full-year
run was started by this continuation.

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T026-live-finalization-profile.md`
FILES CHANGED: `backend/integrations/oanda/source.py`, `backend/tests/integrations/test_oanda_source.py`, this receipt
CHECKS / EVIDENCE: Relevant suites **65 passed, 11 skipped**; focused OANDA/session/fingerprint regressions **56 passed**; Ruff check/format, `compileall`, and `git diff --check` passed. No provider/full-year run.
FINDINGS / CONCERNS: Fresh live snapshot, repeat, and recovery evidence must be rerun by VALIDATE after this correction; guarded PostgreSQL tests were skipped where the local database service was unavailable.

## Final test-contract reconciliation receipt

Updated the stale migration-head assertion in `backend/tests/test_migration_revision.py`
from `0018_acquisition_windows` to the authoritative head `0020_fix_snapshot_guard`.
The revision-length assertion remains unchanged, so migration validation is not weakened.
Checks were run against an isolated schema; the prior suite fixtures tore down
`atlas_test` after stopped-run reuse evidence was captured.

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T026-live-finalization-profile.md`
FILES CHANGED: `backend/tests/test_migration_revision.py`, this receipt
CHECKS / EVIDENCE: `pytest -q backend/tests/test_migration_revision.py` — 2 passed; non-integration backend suite — 328 passed, 7 skipped; Ruff check/format, `compileall`, and `git diff --check` passed. A no-database full-suite attempt yielded 329 passed, 31 skipped, 13 expected integration-fixture errors because `ATLAS_TEST_DATABASE_URL` was unset. No database reset, OANDA/full-year run, branch switch, commit, or runtime/schema/data change.
FINDINGS / CONCERNS: The full integration suite must run on an isolated schema; prior suite fixtures tore down `atlas_test` after stopped-run reuse evidence was captured, so it was not used for this check.
