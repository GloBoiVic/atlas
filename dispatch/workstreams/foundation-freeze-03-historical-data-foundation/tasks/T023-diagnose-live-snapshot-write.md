# T023 — Diagnose live snapshot write

Status: `DONE_WITH_CONCERNS`

Diagnose the remaining real V2 snapshot `DATABASE_WRITE_FAILED` after successful
767,673-bar token-only acquisition. Reproduce snapshot finalization against the
disposable PostgreSQL data without another OANDA load, capture the sanitized root
exception/SQL operation, and fix only the bounded streaming snapshot path. Preserve
append-only immutable facts, exact sparse/native memberships, deterministic
fingerprinting, atomic rollback, and bounded RSS. Add a regression for the diagnosed
failure, then prove snapshot creation/repeat on the existing fresh dataset if possible.
Do not add account-ID requirements, fabricate data, resume the failed provider request,
or change Git history.

## Receipt

ROLE: BUILD
STATUS: DONE_WITH_CONCERNS
ARTIFACT: `dispatch/workstreams/foundation-freeze-03-historical-data-foundation/tasks/T023-diagnose-live-snapshot-write.md`

### Diagnosis

The remaining failure was the bounded `INSERT INTO dataset_snapshot_gaps` batch in
`DatasetSnapshotRepository.create_v2_validated(..., gaps=None)`. Its generated rows
used the literal `policy_version = 'GAP_POLICY_V1'`, while PostgreSQL constraint
`ck_dataset_snapshot_gaps_valid_snapshot_gap` requires the canonical value
`'ATLAS_HISTORICAL_GAP_POLICY_V1'` (the value of domain constant `GAP_POLICY_V1`).
The sanitized database reproduction reported:

```text
constraint ck_dataset_snapshot_gaps_valid_snapshot_gap
statement INSERT INTO dataset_snapshot_gaps (..., policy_version, ...) VALUES (...)
params_redacted <redacted>
```

The failed batch was inside the caller's `session.begin()` transaction, so the
constraint error rolls back the snapshot parent and all membership batches. The
fix replaces both generated literals with the canonical constant. No provider call,
account ID, data fabrication, or immutable-fact update was introduced.

### Files changed

- `backend/persistence/market_data_repository.py`
- `backend/tests/integration/test_market_data_repositories.py`
- this receipt

### Evidence

- `uv run ruff check backend/persistence/market_data_repository.py backend/tests/integration/test_market_data_repositories.py` — clean.
- `uv run pytest -q backend/tests/market_data/test_freeze03_regressions.py` — **9 passed**.
- Added integration regression `test_v2_generated_gaps_use_database_gap_policy`; it is structurally complete but skipped because the repository integration run reports **6 skipped** in this environment.
- Existing disposable PostgreSQL `atlas_test` was probed without OANDA: **767,673** market bars and **0** snapshots before reproduction. A no-provider snapshot-finalization attempt exceeded the 120-second command budget and was terminated; PostgreSQL remained at **0** snapshots / **0** snapshot members, consistent with rollback.
- Direct disposable-PostgreSQL constraint reproduction captured the exact constraint and sanitized SQL above. No secrets or SQL parameters were printed.

CONCERN: The corrected full-year snapshot finalization and repeat were not completed
within the available execution window; no new OANDA acquisition was made. Fresh
validation should run the existing dataset through the corrected path and verify
snapshot counts, fingerprint stability, repeat reuse, and atomic rollback.
