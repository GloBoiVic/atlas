# T021 — Token-only live benchmark correction

Status: `DONE_WITH_CONCERNS`

Correct the benchmark harness/configuration path so historical OANDA validation uses
the existing token-only `OandaHistoricalBarSource` and disposable PostgreSQL test DB;
do not introduce an account-ID requirement. Verify `.env.example` and Settings remain
token-only for historical data. Do not resume the stopped pre-remediation load. Run a
fresh genuine calendar-year load through the actual historical-load/configuration path
and collect all approved performance evidence: OANDA M15/M1 calls/time, market-bar
persistence, planning/coverage, snapshot/fingerprint, total, baseline/peak RSS,
maximum batch/progress payload, repeat time/calls, identical fingerprint/membership,
interrupted/resumed equivalence, and full suite green. Never expose secrets.

## Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T021-token-only-live-benchmark.md`
FILES CHANGED: this receipt only

### Configuration correction

- Verified `Settings`, `.env.example`, `create_app`, and `OandaHistoricalBarSource`:
  historical acquisition requires only `ATLAS_OANDA_API_TOKEN`. No account-ID
  setting or source gate exists; none was added. Token availability was checked
  by presence only and the secret was never printed or persisted.
- Used disposable PostgreSQL `atlas_test`, reset its schema, and migrated cleanly
  to Alembic head. No stopped pre-remediation load was resumed.

### Genuine API benchmark

Ran a fresh `2025-01-01T00:00:00Z` through `2026-01-01T00:00:00Z` request by POSTing
the historical-load API with the catalog StrategyVersion and coordinator-created
`OandaHistoricalBarSource`. OANDA acquisition completed, but snapshot finalization
failed with sanitized `PERSISTENCE / DATABASE_WRITE_FAILED`; no completed snapshot,
fingerprint, repeat, or interrupted/resumed equivalence can be claimed.

- OANDA calls/time: M15 **260 / 124.598s**; M1 **260 / 162.217s**.
- Persistence before failure: **767,673 inserted** reported by API; M15 completed
  units **260**, M1 completed units **520**.
- Planning/coverage: all planned product windows completed; final progress had
  `completed_units=520` and no snapshot.
- Snapshot/fingerprint: **not produced**; status `FAILED`, sanitized
  `DATABASE_WRITE_FAILED`.
- Total **1,707.306s**; baseline RSS **70,557,696 B**; peak RSS
  **1,209,659,392 B**; maximum progress payload **630 B**.
- Batch maximum was not exposed by API telemetry (not claimed). Covered-repeat
  time/calls, identical fingerprint/membership, and interrupted/resumed equivalence
  were not measurable because finalization failed.

### Deterministic and suite evidence

- `uv run python -m backend.market_data.freeze03_benchmark`: all fixture scenarios
  completed. Covered repeat made **0/0** provider calls and retained fingerprint
  `037e9a6fb4a97143dd13a99720904cda9864faaf04039b35714b2a8af647ed01`; interrupted/
  resumed retained the same fingerprint. Maximum batch **2,868**, progress payload
  **417 B**, peak RSS **131,616,768 B**.
- With `ATLAS_TEST_DATABASE_URL` loaded from Settings, `uv run pytest -q backend/tests`:
  **359 passed, 1 skipped, 4 warnings** in **281.84s**.
- One initial suite invocation without exporting the integration URL produced setup
  errors; the correctly configured rerun above is authoritative.

CONCERN: Genuine live evidence is incomplete solely because snapshot persistence
failed after acquisition; no account-ID requirement is a valid blocker.
