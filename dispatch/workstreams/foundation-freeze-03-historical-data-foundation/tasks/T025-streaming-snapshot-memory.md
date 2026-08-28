# T025 — Streaming snapshot memory remediation

Status: `DONE_WITH_CONCERNS`

Fix the measured live snapshot memory/time hotspot only. The coordinator now reaches
snapshot finalization but retains approximately 1.15 GiB RSS and does not complete
within the available window. Audit the actual V2 snapshot stream for hidden ORM/result
buffering, full-year Python collections, and transaction/result lifetime; implement
bounded server-side/keyset streaming and bounded fingerprint/membership operations
without weakening exact sparse/native data, deterministic identity, immutable atomic
snapshots, or crash/resume. Add a large deterministic regression and profile
market-bar persistence separately. Do not start another multi-hour OANDA run until
the bounded snapshot path is proven locally.

## Completion receipt

Replaced authoritative V2 current-bar ORM streams with SQLAlchemy Core column
streams using `stream_results=True`, `max_row_buffer=10_000`, and `yield_per(10_000)`.
They return lightweight rows/domain bars instead of retaining every
`MarketBarModel` in the Session identity map. Generated-gap reads now stream only
the analytical start-time column through Core. Snapshot membership insertion remains
bounded 10,000-row Core executemany inside the existing atomic transaction, and V2
fingerprinting remains incremental; no request-sized membership/gap collection was
introduced.

Added a source regression requiring Core server-side streaming and rejecting ORM
`scalars()` in both authoritative stream methods.

## Checks / profile

- Focused regressions: **10 passed** in **116.01s**.
- Focused plus repository integration command before the final source regression:
  **9 passed, 6 skipped** in **120.07s**; integration database URL was unavailable
  locally. The final focused run is **10 passed**.
- Ruff, `compileall`, and `git diff --check`: passed.
- Deterministic four-scenario benchmark: fresh representative-year total
  **25.787s**, fingerprint **15.969s**, fixture market-bar persistence **1.991s**,
  peak RSS **131,670,016 B**; covered repeat total **19.479s**, fingerprint
  **15.276s**, persistence **2.096s**, peak RSS **131,670,016 B**, with **0/0**
  provider calls. Interrupted/resumed total **24.150s**, fingerprint **13.271s**,
  peak RSS **131,670,016 B**. Fingerprints matched; maximum batch **2,868** and
  progress payload **415 B** (interrupted **417 B**).

The fixture benchmark profiles market-bar persistence separately from planning,
coverage, snapshot, and fingerprint timings; it is not PostgreSQL RSS evidence.

## Remaining gates / concerns

No multi-hour OANDA load was run and no data was reset. The genuine
PostgreSQL/OANDA year benchmark remains required: fresh completion/linkage, exact
sparse/native membership and fingerprint, repeat 0/0 calls, interrupted/resumed
equivalence, and fresh-process RSS under the architecture budget. Capture separate
live PostgreSQL market-bar persistence and snapshot-finalization timings and verify
that Core streaming removes the measured ~1.15 GiB RSS blocker.

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T025-streaming-snapshot-memory.md`
FILES CHANGED: `backend/persistence/market_data_repository.py`, `backend/tests/market_data/test_freeze03_regressions.py`, this receipt
CHECKS / EVIDENCE: bounded Core streams; 10 focused tests; deterministic four-scenario benchmark; Ruff, compileall, and diff check.
FINDINGS / CONCERNS: Live OANDA/PostgreSQL benchmark and live RSS confirmation remain outstanding; integration tests skipped due unavailable local database URL.
