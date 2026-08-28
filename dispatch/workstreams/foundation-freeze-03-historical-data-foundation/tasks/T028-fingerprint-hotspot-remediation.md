# T028 — Fingerprint hotspot remediation

Status: `DONE_WITH_CONCERNS`

Use the completed T027 short representative sample as the only optimization authority.
Fingerprinting is the measured dominant phase (approximately 4.65s of 8.90s in the
representative fresh-year case). Make exactly one narrow, evidence-based remediation
to reduce that cost without changing the canonical V2 fingerprint bytes, member order,
snapshot identity, or bounded-memory contract. Prefer reuse of already persisted
content fingerprints or equivalent canonical work; do not introduce speculative
parallelism, caching with unbounded lifetime, or semantic changes.

Add deterministic regression coverage proving the fingerprint is unchanged and that
fresh/repeat/resumed paths remain equivalent. Re-run the short representative sample
and report before/after fingerprint and total phase timings. Do not start genuine OANDA
or full-year acquisition in this task.

## Receipt

ROLE: BUILD
WORKSTREAM: foundation-freeze-03-historical-data-foundation
BRANCH: `solo/foundation-freeze-03-historical-data-foundation`
CWD: `/Users/vike/Desktop/atlas`
TASK: T028
OWNED_ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T028-fingerprint-hotspot-remediation.md`
STATUS: DONE_WITH_CONCERNS

FILES CHANGED:

- `backend/market_data/fingerprint.py`
- `backend/market_data/ingestion.py`
- `backend/tests/market_data/test_snapshot_v2_contract.py`
- `backend/tests/market_data/test_freeze03_regressions.py`
- This receipt

IMPLEMENTATION:

- Replaced the V2 execution-membership fingerprint pass's temporary `Bar`
  materialization and `Bar.to_json()` call with the same canonical field encoding
  directly from the bounded database row stream. The existing `Bar` implementation
  remains the reference path for membership persistence, so the repository's final
  fingerprint check still rejects any byte mismatch.
- No cache, parallelism, ordering, snapshot identity, database schema, or orchestration
  contract was changed. The stream remains bounded and sparse/native semantics remain
  unchanged.

CHECKS / EVIDENCE:

- `pytest -q backend/tests/market_data/test_snapshot_v2_contract.py backend/tests/market_data/test_freeze03_regressions.py` — 23 passed.
- `pytest -q backend/tests/market_data/test_task3.py backend/tests/market_data/test_one_month_fixture.py` — 25 passed.
- `ruff check` on all four changed Python files — passed.
- `python -m compileall -q` on changed implementation modules — passed.
- `git diff --check` — passed.
- Golden V2 fingerprint bytes are asserted; field-level fingerprint equals the domain
  `Bar` fingerprint; fresh/repeat/resumed fixture fingerprints are asserted equal.
- Short deterministic fixture benchmark, bounded representative year (2024-01-01 to
  2024-02-01; no OANDA/full-year run): T027 receipt reported fingerprint `4,652 ms`
  and total `10,120 ms`; local pre-fix control reported `4,292 ms` and `8,552 ms`;
  post-fix fresh year reported `2,987 ms` and `7,199 ms` (about 30% and 16% below
  the local control). Post-fix repeat reported `2,837 ms` / `5,273 ms`; resumed
  reported `2,827 ms` / `5,763 ms`; all fingerprints remained `c830c458...a6320`.

FINDINGS / CONCERNS:

- `market_bars.content_fingerprint` is intentionally a different persisted market-bar
  variant identity from the V2 `observation_fingerprint` (existing regression coverage
  asserts that distinction), so it could not be substituted without changing snapshot
  bytes/identity. The remediation therefore reuses equivalent canonical field work,
  not that DB hash.
- Genuine credentialed OANDA and full-year acceptance evidence remain outstanding and
  were not started.
